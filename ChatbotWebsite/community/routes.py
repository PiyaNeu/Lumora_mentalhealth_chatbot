from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ChatbotWebsite import db
from ChatbotWebsite.community.moderation import random_alias, screen
from ChatbotWebsite.models import (COMMUNITY_TAGS, REACTIONS, CommunityComment, CommunityPost, CommunityReaction,
                                   CommunityReport)

community = Blueprint("community", __name__)

TITLE_MAX, BODY_MAX, COMMENT_MAX = 120, 2000, 1000


def _visible_post(post_id):
    post = db.session.get(CommunityPost, post_id)
    if post is None or (post.status != "visible" and
                        not (current_user.is_authenticated and post.user_id == current_user.id)):
        abort(404)
    return post


@community.route("/")
def index():
    sort = request.args.get("sort", "recent")
    tag = request.args.get("tag")
    q = CommunityPost.query.filter_by(status="visible")
    if tag in COMMUNITY_TAGS:
        q = q.filter_by(tag=tag)
    if sort == "support":
        support = (db.session.query(CommunityReaction.post_id, func.count().label("n"))
                   .filter(CommunityReaction.kind == "support").group_by(CommunityReaction.post_id).subquery())
        q = q.outerjoin(support, support.c.post_id == CommunityPost.id).order_by(
            func.coalesce(support.c.n, 0).desc(), CommunityPost.created_at.desc())
    else:
        sort = "recent"
        q = q.order_by(CommunityPost.created_at.desc())
    my_pending = []
    if current_user.is_authenticated:
        my_pending = CommunityPost.query.filter(CommunityPost.user_id == current_user.id,
                                                CommunityPost.status != "visible").all()
    return render_template("community/index.html", title="Community", posts=q.limit(50).all(), sort=sort,
                           tag=tag, tags=COMMUNITY_TAGS, reactions=REACTIONS, my_pending=my_pending)


@community.route("/new", methods=["POST"])
@login_required
def new_post():
    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    tag = (request.form.get("tag") or "").strip().lower()
    if not title or not body:
        flash("Please add a title and a message.", "warning")
    elif len(title) > TITLE_MAX or len(body) > BODY_MAX:
        flash(f"Titles can be up to {TITLE_MAX} characters and posts up to {BODY_MAX}.", "warning")
    elif tag not in COMMUNITY_TAGS:
        flash("Please choose one of the allowed tags: " + ", ".join(COMMUNITY_TAGS) + ".", "warning")
    else:
        result = screen(title, body)
        if result.action == "reject":
            flash(result.reason, "danger")
        else:
            post = CommunityPost(user_id=current_user.id, alias=random_alias(), title=title, body=body, tag=tag,
                                 status="visible" if result.action == "ok" else "under_review")
            db.session.add(post)
            db.session.commit()
            if post.status == "under_review":
                flash("Thank you for sharing. Your post is being reviewed before it's shown. It sounds like you "
                      "may be going through something very hard — please use the SOS page to reach a helpline now.",
                      "warning")
                return redirect(url_for("main.sos"))
            flash("Posted anonymously.", "success")
            return redirect(url_for("community.view_post", post_id=post.id))
    return redirect(url_for("community.index"))


@community.route("/post/<int:post_id>")
def view_post(post_id):
    post = _visible_post(post_id)
    comments = [c for c in post.comments if c.status == "visible"
                or (current_user.is_authenticated and c.user_id == current_user.id)]
    mine = set()
    if current_user.is_authenticated:
        mine = {r.kind for r in post.reactions if r.user_id == current_user.id}
    return render_template("community/post.html", title=post.title, post=post, comments=comments,
                           reactions=REACTIONS, mine=mine)


@community.route("/post/<int:post_id>/comment", methods=["POST"])
@login_required
def add_comment(post_id):
    post = _visible_post(post_id)
    body = (request.form.get("body") or "").strip()
    if not body or len(body) > COMMENT_MAX:
        flash(f"Comments must be between 1 and {COMMENT_MAX} characters.", "warning")
        return redirect(url_for("community.view_post", post_id=post.id))
    result = screen(body)
    if result.action == "reject":
        flash(result.reason, "danger")
        return redirect(url_for("community.view_post", post_id=post.id))
    db.session.add(CommunityComment(post_id=post.id, user_id=current_user.id, alias=random_alias(), body=body,
                                    status="visible" if result.action == "ok" else "under_review"))
    db.session.commit()
    if result.action == "under_review":
        flash("Your comment is being reviewed. If you're struggling, please use the SOS page now.", "warning")
    else:
        flash("Comment added.", "success")
    return redirect(url_for("community.view_post", post_id=post.id))


@community.route("/post/<int:post_id>/react/<kind>", methods=["POST"])
@login_required
def react(post_id, kind):
    if kind not in REACTIONS:
        abort(404)
    post = _visible_post(post_id)
    existing = CommunityReaction.query.filter_by(post_id=post.id, user_id=current_user.id, kind=kind).first()
    if existing:
        db.session.delete(existing)  # toggling off
    else:
        db.session.add(CommunityReaction(post_id=post.id, user_id=current_user.id, kind=kind))
    db.session.commit()
    if request.form.get("back") == "feed":
        return redirect(url_for("community.index", sort=request.form.get("sort", "recent")))
    return redirect(url_for("community.view_post", post_id=post.id))


def _report(target_type, target):
    threshold = current_app.config["COMMUNITY_REPORT_THRESHOLD"]
    try:
        db.session.add(CommunityReport(target_type=target_type, target_id=target.id, user_id=current_user.id,
                                       reason=(request.form.get("reason") or "")[:200] or None))
        target.report_count += 1
        if target.report_count >= threshold and target.status == "visible":
            target.status = "hidden"
        db.session.commit()
        flash("Thanks — the report has been recorded.", "info")
    except IntegrityError:
        db.session.rollback()
        flash("You've already reported this.", "info")


@community.route("/post/<int:post_id>/report", methods=["POST"])
@login_required
def report_post(post_id):
    post = _visible_post(post_id)
    _report("post", post)
    return redirect(url_for("community.index") if post.status == "hidden"
                    else url_for("community.view_post", post_id=post.id))


@community.route("/comment/<int:comment_id>/report", methods=["POST"])
@login_required
def report_comment(comment_id):
    comment = db.session.get(CommunityComment, comment_id)
    if comment is None or comment.status != "visible":
        abort(404)
    _report("comment", comment)
    return redirect(url_for("community.view_post", post_id=comment.post_id))


@community.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = db.session.get(CommunityPost, post_id)
    if post is None or post.user_id != current_user.id:
        abort(404)
    CommunityReport.query.filter_by(target_type="post", target_id=post.id).delete()
    db.session.delete(post)
    db.session.commit()
    flash("Your post was deleted.", "info")
    return redirect(url_for("community.index"))
