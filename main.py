from flask import Flask, render_template, redirect, url_for, flash, abort, session
from flask_gravatar import Gravatar
from flask_login import UserMixin, LoginManager, login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import stripe
import psycopg2
import psycopg2.extras
from types import SimpleNamespace
from forms import LoginForm, RegisterForm, NewProductForm, CommentForm, CheckOutForm
import os


SITE_DOMAIN = "https://ecommercesite-for-photos-uygw.onrender.com"

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
stripe.api_key = os.environ.get('STRIPE_API_KEY')

class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        return User(id=user['id'], email=user['email'], name=user['name'])
    return None

gravatar = Gravatar(app,
                   size=100,
                   rating='g',
                   default='retro',
                   force_default=False,
                   force_lower=False,
                   use_ssl=False,
                   base_url=None)


# PostgreSQL connection
def get_db_connection():
    DATABASE_URL = os.environ.get("DB_URL")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)

    return conn

# Create an admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function

@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year, }

# Route to Home page
@app.route('/')
def home():
    return render_template("home.html")


# Register, LogIn & LogOut
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email = %s;", (form.email.data,))
        user_with_same_email = cur.fetchone()
        cur.execute("SELECT * FROM users WHERE name = %s;", (form.name.data,))
        user_with_same_name = cur.fetchone()

        if user_with_same_email:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('register'))
        elif user_with_same_name:
            flash("This name has been taken, please use another name")
            return redirect(url_for('register'))

        hash_and_salted_password = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
        cur.execute("INSERT INTO users (email, name, password) VALUES (%s, %s, %s) RETURNING id;",
                    (form.email.data, form.name.data, hash_and_salted_password))
        user = cur.fetchone()
        user_id = user["id"]
        conn.commit()

        login_user(User(id=user_id, email=form.email.data, name=form.name.data))
        cur.close()
        conn.close()
        return redirect(url_for('home'))

    elif form.email.errors:
        flash("Invalid email format, please enter a valid email address", "error")
        return redirect(url_for('register'))

    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
   form = LoginForm()
   if form.validate_on_submit():
       conn = get_db_connection()
       cur = conn.cursor()

       cur.execute("SELECT * FROM users WHERE email = %s;", (form.email.data,))
       user = cur.fetchone()
       if not user:
           flash("That email has not been registered yet, please try again")
           return redirect(url_for('login'))
       elif not check_password_hash(user["password"], form.password.data):
           flash("The input password is incorrect, please try again")
           return redirect(url_for('login'))
       else:
           login_user(User(id=user["id"], email=user["email"], name=user["name"]))
           cur.close()
           conn.close()
           return redirect(url_for('home'))

   return render_template("login.html", form=form)


@app.route('/logout')
def log_out():
   logout_user()
   return redirect(url_for('home'))

#add, show, edit, remove product
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

      conn = get_db_connection()
      cur = conn.cursor()
      cur.execute("INSERT INTO products (name, description, img_url, price, quantity, stripe_price_id, stripe_product_id) "
                  "VALUES (%s, %s, %s, %s, %s, %s, %s);",
                  (form.name.data, form.description.data, form.img_url.data,
                   form.price.data, form.quantity.data, price.id, product.id))
      conn.commit()
      cur.close()
      conn.close()
      return redirect(url_for('products'))
  return render_template("new_product.html", form=form)


@app.route('/products')
def products():
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("SELECT * FROM products ORDER BY name ASC;")
   all_products_dict = cur.fetchall()
   all_products = [SimpleNamespace(**dict(row)) for row in all_products_dict]
   cur.close()
   conn.close()
   return render_template("products.html", products=all_products)


@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def show_product(product_id):
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("SELECT * FROM products WHERE id = %s;", (product_id,))
   product_dict = cur.fetchone()
   product_object = SimpleNamespace(**product_dict)
   query = """
       WITH filtered_comments AS (
           SELECT id, text, user_id
           FROM comments
           WHERE product_id = %s
       )
       SELECT 
           filtered_comments.id AS comment_id,
           filtered_comments.text,
           filtered_comments.user_id,
           users.name AS user_name,
           users.email
       FROM filtered_comments
       INNER JOIN users ON filtered_comments.user_id = users.id;
       """
   cur.execute(query, (product_id,))
   comments_dict = cur.fetchall()
   comments_object = [SimpleNamespace(**dict(row)) for row in comments_dict]
   comment_form = CommentForm()
   if comment_form.validate_on_submit():
       if not current_user.is_authenticated:
           return redirect(url_for('login'))
       cur.execute("INSERT INTO comments (text, user_id, product_id) VALUES (%s, %s, %s);",
                   (comment_form.text.data, current_user.id, product_id))
       conn.commit()

       return redirect(url_for('show_product', product_id=product_id))

   cur.close()
   conn.close()

   return render_template("show_product.html", product=product_object, comments=comments_object, form=comment_form)


@app.route("/edit/<int:product_id>", methods=["GET", "POST"])
@admin_only
def edit_product(product_id):
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
   product_to_edit_dict = cur.fetchone()
   product_to_edit = SimpleNamespace(**product_to_edit_dict)
   cur.close()

   edit_product_form = NewProductForm(
       img_url=product_to_edit.img_url,
       name=product_to_edit.name,
       description=product_to_edit.description,
       price=product_to_edit.price,
       stripe_price_id=product_to_edit.stripe_price_id,
       quantity=product_to_edit.quantity,
   )
   if edit_product_form.validate_on_submit():
       stripe.Product.modify(
           product_to_edit.stripe_product_id,
           name=edit_product_form.name.data,
           description=edit_product_form.description.data
       )
       edited_price = stripe.Price.create(
           unit_amount=int(edit_product_form.price.data) * 100,
           currency="eur",
           product=product_to_edit.stripe_product_id,
       )
       cur = conn.cursor()
       cur.execute("""
                  UPDATE products SET img_url = %s, name = %s, description = %s,
                  price = %s, quantity = %s, stripe_price_id = %s WHERE id = %s
              """, (
           edit_product_form.img_url.data,
           edit_product_form.name.data,
           edit_product_form.description.data,
           edit_product_form.price.data,
           edit_product_form.quantity.data,
           edited_price.id,
           product_id,
       ))
       conn.commit()
       cur.close()
       conn.close()
       return redirect(url_for('show_product', product_id=product_id))

   return render_template("edit_product.html", product=product_to_edit, form=edit_product_form, is_edit=True)


@app.route("/remove/<int:product_id>")
@admin_only
def remove_product(product_id):
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
   conn.commit()
   cur.close()
   conn.close()
   return redirect(url_for('products'))

#cart
@app.route("/add_to_cart/<int:product_id>")
@login_required
def add_to_cart(product_id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    else:
       conn = get_db_connection()
       cur = conn.cursor()
       cur.execute("SELECT quantity FROM products WHERE id = %s", (product_id,))
       product = cur.fetchone()

       cur.execute(
           "SELECT purchase_quantity FROM product_purchases WHERE product_id=%s AND user_id=%s;",
           (product_id, current_user.id))
       product_record = cur.fetchone()
       if product_record:
           cur.execute("UPDATE product_purchases SET purchase_quantity = purchase_quantity + 1 WHERE product_id = %s AND user_id = %s",
                       (product_id, current_user.id))
           conn.commit()
       else:
           cur.execute(
               "INSERT INTO product_purchases (product_id, user_id, purchase_quantity) "
               "VALUES (%s, %s, %s);",
               (product_id, current_user.id, 1))
           conn.commit()
       cur.close()
       conn.close()
       return redirect(url_for('products'))


@app.route("/remove_from_cart/<int:product_id>")
@login_required
def remove_from_cart(product_id):
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("DELETE FROM product_purchases WHERE user_id = %s AND product_id = %s", (current_user.id, product_id))
   conn.commit()
   cur.close()
   conn.close()
   return redirect(url_for('check_out_products_in_cart'))

#comments
@app.route("/delete_comment/<int:comment_id>")
@login_required
def delete_comment(comment_id):
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("SELECT product_id FROM comments WHERE id = %s", (comment_id,))
   product_id_dict = cur.fetchone()
   product_id = product_id_dict["product_id"]
   cur.execute("DELETE FROM comments WHERE id = %s", (comment_id,))
   conn.commit()
   cur.close()
   conn.close()
   return redirect(url_for('show_product', product_id=product_id))

#single product checkout session, login not required
@app.route('/create-checkout-session/<int:product_id>', methods=["GET", "POST"])
def create_checkout_session(product_id):
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("SELECT id, name, description, img_url, price, quantity, stripe_price_id FROM products WHERE id = %s", (product_id,))
   product_dict = cur.fetchone()
   check_out_product = SimpleNamespace(**product_dict)
   cur.close()
   conn.close()
   session['check_out_product_id'] = product_id
   price_id = check_out_product.stripe_price_id
   check_out_form = CheckOutForm()
   if check_out_form.validate_on_submit():
       try:
           checkout_session = stripe.checkout.Session.create(
               line_items=[{
                   'price': price_id,
                   'quantity': 1,
               }],
               mode='payment',
               success_url=SITE_DOMAIN + '/single_checkout_success',
               cancel_url=SITE_DOMAIN + '/cancel.html',
           )
           return redirect(checkout_session.url, code=303)
       except Exception as e:
           return str(e)

   return render_template("check_out.html", product=check_out_product, form=check_out_form)


@app.route("/single_checkout_success")
def single_checkout_success():
   product_id = session.get('check_out_product_id')
   if not product_id:
       return "No product in session", 400

   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("UPDATE products SET quantity = quantity - 1 WHERE id = %s", (product_id,))
   conn.commit()
   cur.close()
   conn.close()
   return render_template("success.html")


#check out product(s) in cart
@app.route('/check_out_products_in_cart', methods=["GET", "POST"])
@login_required
def check_out_products_in_cart():
   conn = get_db_connection()
   cur = conn.cursor()
   query = """
          WITH products_in_cart AS (
              SELECT product_id, purchase_quantity
              FROM product_purchases
              WHERE user_id = %s
          )
          SELECT 
              products.id,
              products.name,
              products.description,
              products.price,
              products.img_url AS img,
              products_in_cart.purchase_quantity
          FROM products_in_cart
          INNER JOIN products ON products_in_cart.product_id = products.id;
          """
   cur.execute(query, (current_user.id,))
   all_check_out_items = cur.fetchall()
   session['all_check_out_items'] = [dict(row) for row in all_check_out_items]
   cur.close()
   conn.close()

   line_items = [
       {
           'price_data': {
               'currency': 'eur',
               'product_data': {
                   'name': item['name'],
                   'description': item['description'],
               },
               'unit_amount': int(item['price'] * 100),
           },
           'quantity': item['purchase_quantity'],
       }
       for item in all_check_out_items
   ]

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

   return render_template("products_in_cart.html", form=check_out_form, product_dicts=all_check_out_items)

@app.route('/success.html')
def success_url():
   conn = get_db_connection()
   cur = conn.cursor()
   all_check_out_items = session.get('all_check_out_items', [])
   for item in all_check_out_items:
       cur.execute(
           "UPDATE products SET quantity = quantity - %s WHERE id = %s",
           (item['purchase_quantity'], item['id'])
       )
       cur.execute("DELETE FROM product_purchases WHERE product_id = %s AND user_id = %s",
                   (item['id'], current_user.id))
   conn.commit()
   cur.close()
   conn.close()

   return render_template("success.html")


@app.route('/cancel.html')
def cancel_url():
  return render_template("cancel.html")

#about, contact, client
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