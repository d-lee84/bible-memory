import os

from flask import Flask, redirect, render_template, flash, request, abort, url_for, jsonify
from flask_debugtoolbar import DebugToolbarExtension

from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from flask_admin import Admin

from admin import MyAdminIndexView, MTWordModelView

from flask_bootstrap import Bootstrap

from models import db, connect_db, User, Set, SetVerse, Verse
from forms import RegisterForm, LoginForm, DeleteForm, ResetPasswordForm, RequestResetPasswordForm, SetForm

from secret import RECAPTCHA_PRIVATE_KEY, RECAPTCHA_PUBLIC_KEY, EMAIL_PASSWORD, EMAIL_USER

from sets import get_esv_text, get_all_verses

from secrets import token_urlsafe

from flask_mail import Mail, Message

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgresql:///bible_memorization'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")

app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

app.config['RECAPTCHA_PUBLIC_KEY'] = RECAPTCHA_PUBLIC_KEY
app.config['RECAPTCHA_PRIVATE_KEY'] = RECAPTCHA_PRIVATE_KEY

debug = DebugToolbarExtension(app)

connect_db(app)
Bootstrap(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "handle_login"
login_manager.login_message = "Please log in!"


mail_settings = {
    "MAIL_SERVER": 'smtp.gmail.com',
    "MAIL_PORT": 465,
    "MAIL_USE_TLS": False,
    "MAIL_USE_SSL": True,
    "MAIL_USERNAME": EMAIL_USER,
    "MAIL_DEFAULT_SENDER": EMAIL_USER,
    "MAIL_PASSWORD": EMAIL_PASSWORD
}

app.config.update(mail_settings)
mail = Mail(app)

admin = Admin(app,
              name='MTWord',
              template_mode='bootstrap3',
              index_view=MyAdminIndexView())
app.config['FLASK_ADMIN_SWATCH'] = 'journal'


# Administrative views
admin.add_view(MTWordModelView(User, db.session))
admin.add_view(MTWordModelView(Set, db.session))
admin.add_view(MTWordModelView(Verse, db.session))


db.create_all()


####################################################################
# Setting up Login


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


####################################################################
# Error Pages


@app.errorhandler(404)
def show_404_page(err):
    return render_template('errors/404.html'), 404


@app.errorhandler(401)
def show_401_page(err):
    return render_template('errors/401.html'), 401


####################################################################
# Homepage


@app.route("/")
def index():
    """ Show the homepage """
    return render_template("base.html")


@app.route("/explore")
def explore():
    """ Show the first 20 recent sets """
    page = request.args.get('page', 1, type=int)
    sets = Set.query.order_by(Set.created_at.desc()).paginate(page, 10)
    return render_template("explore.html", sets=sets.items, set_paginate=sets)



####################################################################
# Login/Registration Routes


@app.route('/register', methods=["GET", "POST"])
def handle_registration():
    """ Show the registration form or handles the registration
        of a user, if the email or username is taken, take them back to the
        registration form
        - Upon successful login, take to the homepage
    """

    form = RegisterForm()

    email = form.email.data
    username = form.username.data

    # If there is a user with this email already
    if User.query.filter_by(email=email).first():
        form.email.errors = ["This email is already being used"]

    # Check if there is a user with this username already
    if User.query.filter_by(username=username).first():
        form.username.errors = ["This username is already being used"]

    if form.email.errors or form.username.errors:
        return render_template('register.html', form=form)

    if form.validate_on_submit():
        pwd = form.password.data
        f_name = form.first_name.data
        l_name = form.last_name.data

        user = User.register(username=username,
                             pwd=pwd,
                             email=email,
                             f_name=f_name,
                             l_name=l_name)
        db.session.add(user)
        db.session.commit()

        login_user(user)

        flash('Sucessfully logged in!', "success")

        # on successful login, redirect to user detail page
        return redirect(url_for("index"))
    else:
        return render_template("login_register/register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def handle_login():
    """ Shows the login form or handles logging the user in """

    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()

    if form.validate_on_submit():

        # Login and validate the user.
        name = form.username.data
        pwd = form.password.data

        user = User.authenticate(name, pwd)

        if not user:
            form.username.errors = ["Wrong username or password"]
            form.password.errors = ["Wrong username or password"]

            return render_template('login_register/login.html', form=form)

        login_user(user)

        flash('Logged in successfully.', "success")

        return redirect(url_for('index'))

    return render_template('login_register/login.html', form=form)


@app.route("/logout")
def logout():
    """ Logs out the user from the webpage """

    logout_user()

    flash('Sucessfully logged out!', "success")

    return redirect(url_for("index"))


####################################################################
# Reset Password Routes

@app.route("/reset/pw", methods=["GET", "POST"])
def request_reset_pw():

    form = RequestResetPasswordForm()
    email = form.email.data

    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()

        if not user:
            form.email.errors = ["No user found with this email"]
            return render_template("request_reset_pw.html", form=form)

        token = token_urlsafe(16)

        user.password_reset_token = token

        db.session.commit()

        msg = Message("Your password token",
                      recipients=[email])
        msg.html = f"""<p>
                            <a href="http://localhost:5000/reset/pw/{token}">
                                Click here to change your password
                            </a>
                       </p>"""

        mail.send(msg)

        flash("Email has been sent!")

        return redirect("/")

    return render_template("login_register/request_reset_pw.html", form=form)


@app.route("/reset/pw/<token>", methods=["GET", "POST"])
def reset_pw(token):

    form = ResetPasswordForm()
    user = User.query.filter_by(password_reset_token=token).first()

    if not user:
        abort(404)

    if form.validate_on_submit():
        password = form.password.data

        user.update_password(password)

        user.password_reset_token = None

        db.session.commit()

        flash("Your password has been updated!", "success")

        return redirect(url_for("handle_login"))

    return render_template("login_register/reset_pw.html", form=form)


####################################################################
# User Routes

@app.route("/users/<int:user_id>")
def show_user_profile(user_id):
    """ Shows the user profile """


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user_profile(user_id):
    """ Shows the user profile """


@app.route("/users/<int:user_id>/sets")
def show_user_sets(user_id):
    """ Display the user's sets"""

    page = request.args.get("page", 1, type=int)

    searched_user = User.query.get_or_404(user_id)

    sets = Set.query.filter_by(user_id=user_id).paginate(page, 10)

    return render_template("sets/sets_list.html",
                           sets=sets.items,
                           set_paginate=sets,
                           searched_user=searched_user)


####################################################################
# Set Routes


@app.route("/sets/new", methods=["GET", "POST"])
@login_required
def create_new_set():
    """ Creates a new set
        - Validates that there is at least 1 verse reference
    """

    form = SetForm()

    if form.validate_on_submit():

        # Get all the verse instances with the references
        verses = get_all_verses(request.form.getlist('refs'))

        # If there are no valid references
        if not verses:
            form.name.errors = ["Please make sure to include at least 1 valid verse reference"]
            return render_template("sets/add_edit_set.html",
                                   form=form,
                                   title="Add a new set",
                                   verb="Create")

        name = form.name.data

        description = form.description.data

        new_set = Set(name=name,
                      description=description,
                      user_id=current_user.id)

        db.session.add(new_set)
        db.session.commit()

        new_set.verses += verses

        db.session.commit()

        flash("Created new set!", "success")

        return redirect(url_for("show_set", set_id=new_set.id))

    return render_template("sets/add_edit_set.html",
                           form=form,
                           title="Add a new set",
                           verb="Create")


@app.route("/sets/<int:set_id>/edit", methods=["GET", "POST"])
@login_required
def edit_set(set_id):
    """ Display the functionality to the set 
        - Populate the form with data ahead of time 
    """

    form = SetForm()

    current_set = Set.query.get(set_id)

    if current_set.user_id != current_user.id:
        abort(404)

    if form.validate_on_submit():

        # Get all the verse instances with the references
        verses = get_all_verses(request.form.getlist('refs'))

        if not verses:
            form.name.errors = ["Please make sure to include at least 1 valid verse reference"]
            return render_template("sets/add_edit_set.html",
                                   form=form,
                                   title="Edit your set",
                                   verb="Edit",
                                   verses=current_set.verses)

        edited_set = Set.query.get(set_id)

        edited_set.name = form.name.data
        edited_set.description = form.description.data

        edited_set.verses = verses

        db.session.commit()

        flash("Updated your set!", "info")

        return redirect(url_for("show_set", set_id=set_id))

    form = SetForm(obj=current_set)
    return render_template("sets/add_edit_set.html",
                           form=form,
                           title="Edit your set",
                           verb="Edit",
                           verses=current_set.verses)


@app.route("/sets/<int:set_id>")
def show_set(set_id):
    """ Display the set with:
        - Options to edit the set
        - Various studying means
    """

    current_set = Set.query.get_or_404(set_id)

    headers = ("Reference", "Verse")
    verses = current_set.verses

    return render_template("sets/show_set.html",
                           set=current_set,
                           headers=headers,
                           verses=verses)


@app.route("/sets/<int:set_id>/test")
def show_set_test(set_id):
    """  """


@app.route("/sets/<int:set_id>/cards")
def show_set_cards(set_id):
    """ """


@app.route("/sets/<int:set_id>/delete", methods=["POST"])
@login_required
def delete_set(set_id):
    """ Delete the set, (if the set is not found, return 404) """

    current_set = Set.query.get_or_404(set_id)

    # Ensure only the actual user can delete the set
    if current_set.user_id == current_user.id:
        db.session.delete(current_set)
        db.session.commit()

        flash("Your set has been successfully deleted", "success")

        return redirect(url_for("index"))

    flash("You cannot delete someone else's set!", "warning")
    return redirect(request.referrer)


####################################################################
# API Verse Routes


@app.route("/api/verse")
def lookup_verse():
    """ Look up the verse with the reference and return JSON """

    reference = request.args["reference"]
    get_verse_num = request.args["get_verse_num"]

    info = get_esv_text(reference, get_verse_num)

    return jsonify(info=info)
