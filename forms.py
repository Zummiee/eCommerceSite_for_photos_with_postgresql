from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, IntegerField
from wtforms.validators import DataRequired, InputRequired, NumberRange, Email


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Let Me In!")


class RegisterForm(FlaskForm):
    name = StringField("User Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Join")


class NewProductForm(FlaskForm):
    name = StringField("Product Name", validators=[DataRequired()])
    description = StringField("Product Description", validators=[DataRequired()])
    price = StringField("Price", validators=[DataRequired()])
    img_url = StringField("Image URL", validators=[DataRequired()])
    quantity = IntegerField("Number of Products in Stock", validators=[
        InputRequired(message="Quantity is required"),  # Ensure it's filled
        NumberRange(min=1, message="Quantity must be at least 1")  # Enforce a minimum value
    ])
    submit = SubmitField("Submit")


class CommentForm(FlaskForm):
    text = StringField("add comment below", validators=[DataRequired()])
    submit = SubmitField("Add Comment")


class CheckOutForm(FlaskForm):
    submit = SubmitField("Check Out")

#xiumiaokuang@gmail.com
#NewProductForm
