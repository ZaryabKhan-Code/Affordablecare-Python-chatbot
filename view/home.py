from flask import *
from model.oauth import *
from util.salesBot import *
home = Blueprint('home', __name__)


@home.route('/v1')
def v1():
    return render_template('main/v1.html')


@home.route('/v2')
def v2():
    return render_template('main/v2.html')

@home.route('/v3')
def v3():
    return render_template('main/v3.html')

@home.route('/v4')
def v4():
    return render_template('main/v4.html')

@home.route('/v5')
def v5():
    return render_template('main/v5.html')

@home.route('/v6')
def v6():
    return render_template('main/v6.html')

