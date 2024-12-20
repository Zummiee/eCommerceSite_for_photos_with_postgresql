from flask import Flask, abort, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from functools import wraps
from datetime import datetime
from flask_gravatar import Gravatar
import stripe
import os
from forms import LoginForm, RegisterForm, NewProductForm, CommentForm, CheckOutForm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
stripe.api_key = os.environ.get('STRIPE_API_KEY')
SITE_DOMAIN = 'https://ecommercesite-for-photos.onrender.com'
# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# For adding profile images to the comment section
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///purchases.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
# Association table to track purchases (many-to-many)

class ProductPurchase(db.Model):
    __tablename__ = 'product_purchase'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"), nullable=True)
    product_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("products.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)


class Product(db.Model):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(String(250))
    img_url: Mapped[str] = mapped_column(String(250))
    price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    stripe_price_id: Mapped[str] = mapped_column(String(250))
    stripe_product_id: Mapped[str] = mapped_column(String(250))
    buyers: Mapped[list['User']] = relationship("User", secondary="product_purchase", back_populates="products")
    comments: Mapped[list['Comment']] = relationship("Comment", back_populates="parent_product")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    product_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("products.id"), nullable=True)
    products: Mapped[list['Product']] = relationship("Product", secondary="product_purchase", back_populates="buyers")
    product_comments: Mapped[list['Comment']] = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"), nullable=True)
    product_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("products.id"), nullable=True)
    parent_product = relationship("Product", back_populates="comments")
    comment_author = relationship("User", back_populates="product_comments")


with app.app_context():
    db.create_all()


# Create an admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function


@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year, }


@app.route('/')
def home():
    return render_template("home.html")


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        result_email = db.session.execute(db.select(User).where(User.email == form.email.data))
        user_with_same_email = result_email.scalar()
        result_name = db.session.execute(db.select(User).where(User.name == form.name.data))
        user_with_same_name = result_name.scalar()
        if user_with_same_email:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('register'))
        elif user_with_same_name:
            flash("This name has been taken, please use another name")
            return redirect(url_for('register'))
        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for('home'))
    elif form.email.errors:
        flash("Invalid email format, please enter a valid email address.", "error")
        return redirect(url_for('register'))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        result_email = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result_email.scalar()
        input_password = form.password.data
        if not user:
            flash("That email has not been registered yet, please try again")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, input_password):
            flash("The input password is incorrect, please try again")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('home'))
    return render_template("login.html", form=form)


@app.route('/logout')
def log_out():
    logout_user()
    return redirect(url_for('home'))


@app.route('/add_product', methods=["GET", "POST"])
@admin_only
def add_product():
    form = NewProductForm()
    if form.validate_on_submit():
        product = stripe.Product.create(name=form.name.data,
                                        description=form.description.data,
                                        )
        price = stripe.Price.create(
            unit_amount=int(form.price.data) * 100,  # price in cents (e.g., $10.00)
            currency="eur",
            product=product.id,
        )

        new_product = Product(img_url=form.img_url.data,
                              name=form.name.data,
                              description=form.description.data,
                              price=form.price.data,
                              stripe_price_id=price.id,
                              stripe_product_id=product.id,
                              quantity=form.quantity.data,
                              )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('products'))
    return render_template("new_product.html", form=form)


@app.route('/products')
def products():
    result = db.session.execute(db.select(Product))
    product_list = result.scalars().all()
    return render_template("products.html", products=product_list)


@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def show_product(product_id):
    requested_product = db.get_or_404(Product, product_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        new_comment = Comment(text=comment_form.text.data,
                              parent_product=requested_product,
                              comment_author=current_user
                              )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_product', product_id=requested_product.id))
    return render_template("show_product.html", product=requested_product, form=comment_form)


@app.route("/edit/<int:product_id>", methods=["GET", "POST"])
@admin_only
def edit_product(product_id):
    product_to_edit = db.get_or_404(Product, product_id)
    edit_product_form = NewProductForm(
        img_url=product_to_edit.img_url,
        name=product_to_edit.name,
        description=product_to_edit.description,
        price=product_to_edit.price,
        stripe_price_id=product_to_edit.stripe_price_id,
        quantity=product_to_edit.quantity,
    )
    if edit_product_form.validate_on_submit():
        stripe_product = stripe.Product.modify(
            product_to_edit.stripe_product_id,  # Stripe product ID
            name=edit_product_form.name.data,  # New name from the form
            description=edit_product_form.description.data  # New description from the form
        )
        edited_price = stripe.Price.create(
            unit_amount=int(edit_product_form.price.data) * 100,  # price in cents (e.g., $10.00)
            currency="eur",
            product=product_to_edit.stripe_product_id,
        )
        product_to_edit.stripe_price_id = edited_price.id
        product_to_edit.img_url = edit_product_form.img_url.data
        product_to_edit.name = edit_product_form.name.data
        product_to_edit.description = edit_product_form.description.data
        product_to_edit.price = edit_product_form.price.data
        product_to_edit.quantity = edit_product_form.quantity.data
        db.session.commit()
        return redirect(url_for('show_product', product_id=product_to_edit.id))
    return render_template("edit_product.html", product=product_to_edit, form=edit_product_form, is_edit=True)


@app.route("/remove/<int:product_id>")
@admin_only
def remove_product(product_id):
    product_to_remove = db.get_or_404(Product, product_id)
    db.session.delete(product_to_remove)
    db.session.commit()
    return redirect(url_for('products'))


@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    if current_user.is_authenticated:
        existing_record = ProductPurchase.query.filter_by(
            buyer_id=current_user.id,
            product_id=product_id
        ).one_or_none()
        if existing_record:
            existing_record.quantity += 1
        else:
            new_purchase_record = ProductPurchase(
                buyer_id=current_user.id,
                product_id=product_id,
                quantity=1
            )
            db.session.add(new_purchase_record)
        db.session.commit()
        return redirect(url_for('products'))
    else:
        return redirect(url_for('login'))


@app.route("/remove_from_cart/<int:product_id>")
def remove_from_cart(product_id):
    product_to_remove = db.get_or_404(Product, product_id)
    relevant_purchase_record = ProductPurchase.query.filter_by(
        buyer_id=current_user.id,
        product_id=product_id,
    ).one_or_none()
    if relevant_purchase_record:
        db.session.flush()
        db.session.delete(relevant_purchase_record)
        db.session.commit()
    if product_to_remove in current_user.products:
        current_user.products.remove(product_to_remove)
    if current_user in product_to_remove.buyers:
        product_to_remove.buyers.remove(current_user)
    db.session.commit()
    return redirect(url_for('check_out_products_in_cart'))


@app.route("/delete_comment/<int:comment_id>")
def delete_comment(comment_id):
    comment_to_remove = db.get_or_404(Comment, comment_id)
    relevant_product_id = comment_to_remove.parent_product.id
    db.session.delete(comment_to_remove)
    db.session.commit()
    return redirect(url_for('show_product', product_id=relevant_product_id))


@app.route('/create-checkout-session/<int:product_id>', methods=["GET", "POST"])
def create_checkout_session(product_id):
    check_out_product = db.get_or_404(Product, product_id)
    session['check_out_product_id'] = product_id
    price_id = check_out_product.stripe_price_id
    check_out_form = CheckOutForm()
    if check_out_form.validate_on_submit():
        try:
            checkout_session = stripe.checkout.Session.create(
                line_items=[
                    {
                        'price': price_id,
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url=SITE_DOMAIN + '/single_checkout_success',
                cancel_url=SITE_DOMAIN + '/cancel.html',
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            return str(e)
    return render_template("check_out.html", product=check_out_product, form=check_out_form)


@app.route('/check_out_products_in_cart', methods=["GET", "POST"])
def check_out_products_in_cart():
    all_check_out_items = []
    line_items = []
    all_check_out_products = list(current_user.products)
    for product in all_check_out_products:
        purchase_record = ProductPurchase.query.filter_by(
            buyer_id=current_user.id,
            product_id=product.id
        ).one_or_none()

        if purchase_record:
            product_dict = {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'img': product.img_url,
                'purchase_quantity': purchase_record.quantity,
            }
            all_check_out_items.append(product_dict)
    session['all_check_out_items'] = all_check_out_items

    for item in all_check_out_items:
        line_items.append({
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': item['name'],
                    'description': item['description'],
                },
                'unit_amount': int(item['price'] * 100),
            },
            'quantity': item['purchase_quantity'],
        })
    check_out_form = CheckOutForm()
    if check_out_form.validate_on_submit():
        try:
            checkout_session = stripe.checkout.Session.create(
                line_items=line_items,
                mode='payment',
                success_url=SITE_DOMAIN + '/success.html',
                cancel_url=SITE_DOMAIN + '/cancel.html',
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            return str(e)
    return render_template("products_in_cart.html", products=all_check_out_products,
                           form=check_out_form, product_dicts=all_check_out_items)


@app.route('/success.html')
def success_url():
    all_check_out_items = session.get('all_check_out_items', [])
    all_check_out_products = list(current_user.products)
    for check_out_product in all_check_out_products:
        relevant_purchase_record = ProductPurchase.query.filter_by(
            buyer_id=current_user.id,
            product_id=check_out_product.id
        ).one_or_none()
        if relevant_purchase_record:
            db.session.flush()
            db.session.delete(relevant_purchase_record)
            db.session.commit()
        relevant_product_dict = next((product_dict for product_dict in all_check_out_items
                                      if product_dict['name'] == check_out_product.name), None)
        check_out_product.quantity -= relevant_product_dict['purchase_quantity']
        if check_out_product in current_user.products:
            current_user.products.remove(check_out_product)
        if current_user in check_out_product.buyers:
            check_out_product.buyers.remove(current_user)
    db.session.commit()
    return render_template("success.html")


@app.route('/single_checkout_success')
def single_checkout_success():
    check_out_product_id = session.get('check_out_product_id', [])
    check_out_product = db.get_or_404(Product, check_out_product_id)
    check_out_product.quantity -= 1
    db.session.commit()
    return render_template("success.html")


@app.route('/cancel.html')
def cancel_url():
    return render_template("cancel.html")


@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/contact')
def contact():
    return render_template("contact.html")


@app.route('/client')
def client():
    return render_template("client.html")


if __name__ == "__main__":
    app.run(debug=False)
