from flask import Flask, render_template, redirect, url_for, flash, g, abort
from functools import wraps
from flask.globals import request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from flask_wtf import form
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import (
    UserMixin,
    login_user,
    LoginManager,
    login_required,
    current_user,
    logout_user,
)
from forms import CreatePostForm, RegisterForm, LogInForm, CommentForm
from flask_gravatar import Gravatar

app = Flask(__name__)
login_manager = LoginManager()
app.config["SECRET_KEY"] = "8BYkEfBA6O6donzWlSihBXox7C0sKR6b"
ckeditor = CKEditor(app)
login_manager.init_app(app)
Bootstrap(app)


##CONNECT TO DB
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///blog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


gravatar = Gravatar(
    app,
    size=300,
    rating="g",
    default="retro",
    force_default=False,
    force_lower=False,
    use_ssl=False,
    base_url=None,
)

##CONFIGURE TABLES


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    comments = relationship("Comment", back_populates="parent_post")
    img_url = db.Column(db.String(250), nullable=False)


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    text = db.Column(db.String(1000), nullable=False)


db.create_all()


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route("/")
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template(
        "index.html",
        all_posts=posts,
        logged_in=current_user.is_authenticated,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if request.method == "POST" and register_form.validate_on_submit():
        new_user = User(
            email=register_form.email.data,
            password=generate_password_hash(
                password=register_form.password.data,
                salt_length=8,
                method="pbkdf2:sha256",
            ),
            name=register_form.name.data,
        )
        if User.query.filter_by(email=new_user.email).first():
            flash(
                message=f"Email already exists! Login with the email.",
                category="error",
            )
            return redirect(url_for("login"))
        else:
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(
                url_for(
                    "get_all_posts",
                    logged_in=current_user.is_authenticated,
                )
            )
    return render_template(
        "register.html",
        form=register_form,
        logged_in=current_user.is_authenticated,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    login_form = LogInForm()
    if request.method == "POST" and login_form.validate_on_submit():
        entered_password = login_form.password.data
        entered_email = login_form.email.data
        user = User.query.filter_by(email=entered_email).first()
        if not user:
            flash(
                message="Email not found. Try again!",
                category="error",
            )
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, entered_password):
            flash(message="Invalid Password!! Try again", category="error")
        else:
            login_user(user)
            return redirect(
                url_for(
                    "get_all_posts",
                    logged_in=current_user.is_authenticated,
                )
            )
    return render_template(
        "login.html",
        form=login_form,
        logged_in=current_user.is_authenticated,
    )


@app.route("/logout")
def logout():
    logout_user()
    return redirect(
        url_for(
            "get_all_posts",
            logged_in=current_user.is_authenticated,
        )
    )


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comments = requested_post.comments
    comment_form = CommentForm()
    if request.method == "POST" and comment_form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=comment_form.comment_text.data,
                parent_post=requested_post,
                comment_author=current_user,
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=requested_post.id))
        else:
            flash(message="Log In to Comment", category="error")
            return redirect(url_for("login"))
    return render_template(
        "post.html",
        post=requested_post,
        form=comment_form,
        post_comments=comments,
        logged_in=current_user.is_authenticated,
    )


@app.route("/about")
def about():
    return render_template(
        "about.html",
        logged_in=current_user.is_authenticated,
    )


@app.route("/contact")
def contact():
    return render_template(
        "contact.html",
        logged_in=current_user.is_authenticated,
    )


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(
            url_for(
                "get_all_posts",
                logged_in=current_user.is_authenticated,
            )
        )
    return render_template(
        "make-post.html",
        form=form,
        logged_in=current_user.is_authenticated,
    )


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(
            url_for(
                "show_post",
                post_id=post.id,
                logged_in=current_user.is_authenticated,
            )
        )

    return render_template(
        "make-post.html",
        form=edit_form,
        logged_in=current_user.is_authenticated,
    )


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    if current_user.is_authenticated():
        post_to_delete = BlogPost.query.get(post_id)
        db.session.delete(post_to_delete)
        db.session.commit()
        return redirect(
            url_for(
                "get_all_posts",
                logged_in=current_user.is_authenticated,
            )
        )
    else:
        return redirect(
            url_for(
                "get_all_posts",
                logged_in=current_user.is_authenticated,
            )
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
