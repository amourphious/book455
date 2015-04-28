import webapp2
import cgi
import re
import os
import logging
import jinja2
import random
import string
import hashlib
import urllib2
import json

from xml.dom.minidom import Document
from xml.dom import minidom

from datetime import datetime, timedelta
from collections import namedtuple

from google.appengine.api import urlfetch
from google.appengine.api import mail 
from google.appengine.ext import db
from google.appengine.api import images
from google.appengine.api import users


template_dir=os.path.join(os.path.dirname(__file__),'templates')
jinja_env=jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),autoescape = True)

ISBN_RE=re.compile(r"^[0-9]{1,13}$")

class user(db.Model):
	password = db.StringProperty(required=True)
	name = db.StringProperty(required=True)
	email_id = db.StringProperty(required=True)
	userType = db.StringProperty(required=True)
	
class Book(db.Model):
	isbn = db.StringProperty(required=True)
	name = db.StringProperty(required=True)
	author = db.StringProperty(required=True)
	qty = db.IntegerProperty(required =True)
	book_img = db.StringProperty()
	lang = db.StringProperty()
	description = db.TextProperty()
	rating = db.FloatProperty()
	pages = db.IntegerProperty()
	book_format = db.StringProperty()
	gr_link = db.StringProperty()
	
	@staticmethod
	@db.transactional
	def book_purchase_request(book_id):
		book = db.get(book_id)
		if book and book.qty > 0:
			book.qty = book.qty -1
			return book.put()
		else:
			return None
	
	@staticmethod
	@db.transactional
	def add_book(qty, key):
		book = db.get(key)
		book.qty = book.qty + int(qty)
		return  book.put()
		
	def id(self):
		a = self.key()
		b = a.id()
		return b	


order_state  = ["Placed", "Approved", "Shipped", "Canceled", "Delivered"]

class Order(db.Model):
	user=db.StringProperty(required=True)
	book=db.StringProperty(required=True)
	status=db.IntegerProperty(required=True)
	placed_time = db.DateTimeProperty(required=True)
	approved_time = db.DateTimeProperty()
	shipped_time = db.DateTimeProperty()
	delivered_time = db.DateTimeProperty()
	cancel_time = db.DateTimeProperty()
	deliver_to=db.StringProperty(required=True)
	
	def id(self):
		a = self.key()
		b = a.id()
		return b
		
	@staticmethod
	@db.transactional(xg=True)
	def changeStatus(order_no, status, user_type):
		order = db.get(order_no)
		if order:
			if user_type == 0:
				if status == 3 and order.status < 3:
					order.status = status
					order.cancel_time = datetime.now()
					Book.add_book(1, order.book)
			else:
				if status > order.status and status < 5 and (not order.status == 3):
					order.status = status
					if status == 1:
						order.approved_time = datetime.now()
					elif status == 2:
						order.shipped_time = datetime.now()
					elif status == 3:
						order.cancel_time = datetime.now()
						Book.add_book(1, order.book)
					else:
						order.delivered_time = datetime.now()
		return order.put()

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a,**kw)
		
	def render_str(self,template,**params):
		t=jinja_env.get_template(template)
		return t.render(params)
		
	def render(self,template,**kw):
		self.write(self.render_str(template,**kw))
		
def hash_str(s):
	return hashlib.sha256(s).hexdigest()
	


def make_salt():
	return ''.join(random.choice(string.letters) for x in xrange(5))
	


def make_pw_hash(name,pw,salt=None):
	if not salt:
		salt=make_salt()
	h=hashlib.sha256(name+pw+salt).hexdigest()
	return "%s|%s" %(h,salt)
	

    
def valid_pw(name,pw,h):
	salt=h.split('|')[1]
	return make_pw_hash(name,pw,salt)

def valid_login(name,pw,h):
	salt=h.split('|')[1]
	return (make_pw_hash(name,pw,salt) == h)

class Login(Handler):
	def get(self):
		self.render("index.html", login_error="")
	
	def post(self):
		username = self.request.get("login_username")
		password = self.request.get("login_password")
		user =  db.GqlQuery("select * from user where email_id ='" + username + "'")
		user = list(user)
		i = 0
		for us in user:
			i = i+1
			logging.error(us.email_id + " " + us.password)
		if(i > 0):
			if(valid_login(username, password, str(user[0].password))):
				self.response.headers.add_header('Set-Cookie',"name=%s ; Path=/" % str(user[0].password))
				self.redirect("/index")
			else:
				self.render("index.html", login_error = "invalid credentials")
		else:
			self.render("index.html", login_error = "invalid credentials no user")
			
			
class Signup(Handler):
	def get(self):
		self.render("index.html", signup_error="")
	
	def post(self):
		password=self.request.get("signup_password")
		name = self.request.get("signup_name")
		email = self.request.get("signup_email")
		User =  db.GqlQuery("select * from user where email_id ='" + email + "'")
		User = list(User)
		i = 0
		for us in User:
			i = i+1
			logging.error(us.email_id + " " + us.password)
		if(i == 0):
			hashed_password=make_pw_hash(email,password)
			new_user=user(password=hashed_password,name = name, email_id = email, userType='0')
			logging.error("Creating User" + email+ " " + hashed_password)
			a_key=new_user.put()
			self.response.headers.add_header('Set-Cookie',"name=%s ; Path=/" % str(hashed_password))
			self.redirect("/index")
		else:
			self.render("index.html", signup_error = "user Exists !")	
			
class Book455(Handler):
	def get(self):
		cookie = self.request.cookies.get("name")
		user = None
		books = None
		books = db.GqlQuery("select * from Book")
		books = list(books)
		if len(books) <= 0:
			books = None
			n = 0
		else:
			n = len(books)
		if cookie == "" or cookie == None:
			logging.error(cookie)
		else:
			user =  db.GqlQuery("select * from user where password ='" + cookie + "'")
			user = list(user)
			if len(user) > 0:
				user = user[0]
			else:
				user = None
		self.render("index.html", user = user, books = books, n = n)
				


class BookAdd(Handler):
	def get(self):
		cookie = self.request.cookies.get("name")
		if cookie == "" or cookie == None:
			self.render("index.html")
		else:
			user =  db.GqlQuery("select * from user where password ='" + cookie + "'")
			if(user and user[0].userType == '1'):
				books = db.GqlQuery("select * from Book")
				books = list(books)
				self.render("book_add.html", books = books)
			else:
				self.redirect("/index")
		
	def getBookProperty(self, book, prop):
		if len(book.getElementsByTagName(prop)) > 0:
			book_prop = book.getElementsByTagName(prop)[0]
			if len(book_prop.childNodes) > 0:
				return book_prop.childNodes[0].data
		return None
		
	def post(self):
		isbn = self.request.get("ISBN")
		isbn = isbn.replace(" ", "")
		qty = self.request.get("qty")
		qty = qty.replace(" ", "")
		logging.error(repr(ISBN_RE.match(isbn)))
		logging.error(ISBN_RE.match(qty))
		if isbn and qty:
			book_list =  db.GqlQuery("select * from Book where isbn='" + isbn+ "'")
			logging.error("book")
			book_list = list(book_list)
			if len(book_list) > 0:
				logging.error("book already present")
				Book.add_book(qty, book_list[0].key())
				self.redirect("/add_book")
				return
		url = "https://www.goodreads.com/book/isbn?key=EQE829dxVCEFRGpamU8vQ&isbn=" + isbn
		try:
			logging.error("querying")
			contents = urlfetch.fetch(url).content
			results = minidom.parseString(contents)
			book_data = results.getElementsByTagName("book")[0]
			book_name = self.getBookProperty(book_data, "title")
			book_img = self.getBookProperty(book_data, "image_url")
			book_lang = self.getBookProperty(book_data, "language_code")
			book_desc = self.getBookProperty(book_data, "description")
			book_rating = self.getBookProperty(book_data, "average_rating")
			book_pages = self.getBookProperty(book_data, "num_pages")
			book_format = self.getBookProperty(book_data, "format")
			book_gr_link = self.getBookProperty(book_data, "link")
			authors_str = ""
			if len(book_data.getElementsByTagName("authors")) > 0:
				book_authors =  book_data.getElementsByTagName("authors")[0]
				book_author = book_authors.getElementsByTagName("author")
				
				for author in book_author:
					authors_str += author.getElementsByTagName("name")[0].childNodes[0].data + " "
					
			if book_name and authors_str and qty > 0 and isbn != "" :
				new_book = Book(isbn = isbn, 
											name = book_name, 
											author = authors_str, 
											qty = int(qty),  
											book_img = book_img, 
											lang = book_lang, 
											description = book_desc, 
											rating = float(book_rating), 
											pages = int(book_pages) if (book_pages != None)  else  None, 
											book_format = book_format, 
											gr_link = book_gr_link)
				book_key = new_book.put()
				self.redirect("/add_book")
		except Exception as e:
			self.write(repr(e))

class BookPermalink(Handler):
	def get(self, book_id):
		cookie = self.request.cookies.get('name')
		user = None
		if cookie:
			user = db.GqlQuery("select * from user where password ='" + cookie + "'")
			user = user[0]
		book = Book.get_by_id(int(book_id))
		self.render("book_link.html", book = book, user = user)
		
class BuyBook(Handler):
	def post(self):
		user = self.request.get('user')
		book= self.request.get('book')
		deliver_to = "tathagat tut"
		status=0
		placed_time=datetime.now()
		if Book.book_purchase_request(book):
			order = Order( user = user, book = book, deliver_to = deliver_to, status = status, placed_time = placed_time)
			order_key = order.put()
			self.redirect('/orders')
		else:
			self.redirect('/index')
		
class BookOrder(Handler):
	def get(self):
		cookie = self.request.cookies.get("name")
		if cookie == "" or cookie == None:
			self.redirect("/index")
		else:
			user =  db.GqlQuery("select * from user where password ='" + cookie + "'")
			if len(list(user)) < 1:
				self.redirect('/index')
				return
			if(user and user[0].userType == '1'):
				orders = db.GqlQuery("select * from Order ORDER BY placed_time DESC")
				orders = list(orders)
				books = []
				users = []
				for order in orders:
					books.append(db.get(order.book))
					users.append(db.get(order.user))
				self.render("orders.html", orders = orders, books = books, users = users, user = user[0])
			else:
				orders = db.GqlQuery("select * from Order where user='"+ str(user[0].key()) + "' ORDER BY placed_time DESC")
				books = []
				users = []
				orders = list(orders)
				for order in orders:
					books.append(db.get(order.book))
				self.render("orders.html", orders = orders, books = books, user = user[0])

	def post(self):
		order_no = self.request.get('order_no')
		status = self.request.get('status')
		user_type = self.request.get('user_type')
		Order.changeStatus(order_no, int(status), int(user_type))
		self.redirect('./orders')
				
		
		
		
		
app = webapp2.WSGIApplication([ ('/index' , Book455),
								('/login', Login),
								('/signup' , Signup),
								('/add_book', BookAdd),
								('/book/([0-9]+)', BookPermalink),
								("/buy", BuyBook),
								('/orders', BookOrder)],
								 debug=True)
