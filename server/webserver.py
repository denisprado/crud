import os
import tempfile
from flask import Flask, flash, render_template, request, redirect, url_for
from flask import jsonify, send_from_directory
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from database_setup import Base, Foto, Tema, Arte, Festa
from database_setup import Produto, Objeto, User
from werkzeug.utils import secure_filename
from flask import session as login_session
import random
import string
from functools import wraps

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

APPLICATION_nome = "Festa de Papel"

UPLOAD_FOLDER = "uploads/fotos"
ALLOWED_EXTENSIONS = set(["jpg", "gif", "png", "jpge", "cdr"])

app = Flask(__name__, static_folder="../static/dist/css/",
            template_folder="../static/templates",
            static_url_path="/static/dist/css")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config.from_object(__name__)

engine = create_engine('sqlite:///festas_de_papel.db',
                       connect_args={'check_same_thread': False})
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            return redirect(url_for('showLogin'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    print("ok state")
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Usuario ja está conectado.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # verifica e cria conta se ele n existir
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 50px">'
    flash("you are now logged in as %s" % login_session['username'])
    print("done!")
    return output

# User Helper Functions


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print('Access Token is None')
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print('In gdisconnect access token is %s'), access_token
    print('User nome is: ')
    print(login_session['username'])
    url_initial = 'https://accounts.google.com/o/oauth2/revoke?'
    url = url_initial + 'token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print('result is ')
    print(result)
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Desconectado!.'), 200)
        response.headers['Content-Type'] = 'application/json'
        flash("desconectado")
        return redirect(url_for('index'))
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/')
def index():
    if 'username' not in login_session:
        return redirect(url_for('showLogin'))

    return redirect(url_for('listArte'))


@app.route('/produto/<filename>')
@app.route('/foto/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ##### FOTOS ######
@app.route('/fotos')
@login_required
def listFoto():
    fotos = session.query(Foto).all()
    fields = [["input", "Nome", "nome", "required"], [
        "textarea", "Descrição", "descricao", "required"]]
    return render_template('listFORM.html', fields=fields, fotos=fotos,
                           table="Foto", var_table=fotos)


@app.route('/foto/<int:id>',
           methods=['GET', 'POST'])
@login_required
def showFoto(id):
    editedFoto = session.query(Foto).filter_by(id=id).one()
    fields = [["textarea", "Descrição", "descricao", "required",
               editedFoto.descricao], ["file", "Arquivo", "file", "required",
                                       editedFoto.caminho]]
    return render_template('showFORM.html', id=id, fields=fields,
                           editing=editedFoto, table="Foto")


@app.route('/foto/new', methods=['POST', 'GET'])
@login_required
def newFoto():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash(request.files)
            flash("Sem arquivo")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash("Arquivo nao selecionado")
            return redirect(request.url)
        if file and allowed_file(file.filename):

            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            newFoto = Foto(caminho=filename,
                           descricao=request.form['descricao'])
            session.add(newFoto)
            session.commit()
            return redirect(url_for('listFoto'))
    fields = [["file", "Arquivo", "file", "required"], [
        "textarea", "Descrição", "descricao", "required"]]
    return render_template('newFORM.html', fields=fields, table="Foto")


@app.route('/foto/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editFoto(id):
    editedFoto = session.query(Foto).filter_by(id=id).one()
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            editedFoto.caminho = filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            session.add(editedFoto)
            session.commit()
            flash("Nova foto adicionada")
        if request.form['descricao']:
            editedFoto.descricao = request.form['descricao']
        return redirect(url_for('listFoto'))
    else:
        fields = [["textarea", "Descrição", "descricao",
                   editedFoto.descricao], ["file", "Arquivo", "file",
                                           "required", editedFoto.caminho]]
        return render_template('editFORM.html', id=id, fields=fields,
                               editing=editedFoto, table="Foto")


@app.route('/foto/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteFoto(id):
    fotoToDelete = session.query(Foto).filter_by(id=id).one()
    if request.method == 'POST':
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], url_for(
            'uploaded_file', filename=fotoToDelete.caminho)))
        session.delete(fotoToDelete)
        session.commit()
        return redirect(url_for('listFoto'))
    else:
        return render_template('deleteFORM.html', record=fotoToDelete,
                               table="Foto")


# ##### PRODUTOS ######
@app.route('/produtos')
@login_required
def listProduto():
    produtos = session.query(Produto).all()
    fields = [["input", "Descrição", "descricao",
               "required"], ["input", "Valor", "valor", "required"]]
    return render_template('listFORM.html', table="Produto",
                           var_table=produtos, fields=fields)


@app.route('/produto/new', methods=['POST', 'GET'])
@login_required
def newProduto():
    # tipos = session.query(tipoProduto).all()
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("Sem arquivo")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash("Arquivo nao selecionado")
            return redirect(request.url)
        if file and allowed_file(file.filename):

            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            newProduto = Produto(
                caminho=filename, descricao=request.form["descricao"],
                valor=request.form['valor'])
            session.add(newProduto)
            session.commit()
            return redirect(url_for('listProduto'))
    fields = [["file", "Arquivo", "file", "required"], [
        "textarea", "Descrição", "descricao"], ["input", "Valor", "valor",
                                                "required"]]
    return render_template('newFORM.html', fields=fields, table="Produto")


@app.route('/produto/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editProduto(id):
    editedProduto = session.query(Produto).filter_by(id=id).one()
    if request.method == 'POST':
        file = request.files['file']
        print(request.files)
        if file:
            filename = secure_filename(file.filename)
            editedProduto.caminho = filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            session.add(editedProduto)
            session.commit()
            return redirect(url_for('listProduto'))
    else:
        fields = [["file", "Arquivo", "file", "required",
                   editedProduto.caminho], ["textarea", "Descrição",
                                            "descricao",
                                            editedProduto.descricao],
                  ["input", "Valor", "valor", "", editedProduto.valor]]
        return render_template('editFORM.html', id=id,
                               fields=fields, editing=editedProduto,
                               table="Produto")


@app.route('/produto/<int:id>',
           methods=['GET', 'POST'])
@login_required
def showProduto(id):
    editedProduto = session.query(Produto).filter_by(id=id).one()
    if request.method == 'POST':
        file = request.files['file']
        print(request.files)
        if file:
            filename = secure_filename(file.filename)
            editedProduto.caminho = filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            session.add(editedProduto)
            session.commit()
            return redirect(url_for('listProduto'))
    else:
        fields = [["textarea", "Descrição", "descricao", "required",
                   editedProduto.descricao], [
            "input", "Valor", "valor", "", editedProduto.valor]]
        return render_template('showFORM.html', id=id, fields=fields,
                               editing=editedProduto, table="Produto")


@app.route('/produto/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteProduto(id):
    produtoToDelete = session.query(Produto).filter_by(id=id).one()
    if request.method == 'POST':
        session.delete(produtoToDelete)
        session.commit()
        return redirect(url_for('listProduto'))
    else:
        return render_template('deleteFORM.html', record=produtoToDelete,
                               table="Produto")

# ##### TEMAS ######


@app.route('/temas')
@login_required
def listTema():
    fotos = session.query(Foto).all()
    temas = session.query(Tema).all()
    fields = [["input", "Nome", "nome", "required"], [
        "textarea", "Descrição", "descricao", "required"]]
    return render_template('listFORM.html', id=id, fields=fields, fotos=fotos,
                           table="Tema", var_table=temas)


@app.route('/tema/new', methods=['GET', 'POST'])
@login_required
def newTema():
    fotos = session.query(Foto).all()
    if request.method == 'POST':  # response from template form
        newTema = Tema(nome=request.form['nome'], descricao=request.form[
            'descricao'], foto=request.form['foto'])
        session.add(newTema)
        session.commit()
        return redirect(url_for('listTema'))
    else:
        fields = [["input", "Nome", "nome", "required"],
                  ["textarea", "Descrição", "descricao"]]
        radio = ["foto", fotos]
        return render_template('newFORM.html', fotos=radio, fields=fields,
                               table="Tema")


@app.route('/tema/<int:id>',
           methods=['GET', 'POST'])
@login_required
def showTema(id):
    fotos = session.query(Foto).all()
    editedTema = session.query(Tema).filter_by(id=id).one()
    fields = [["input", "Nome", "nome", "required", editedTema.nome], [
        "textarea", "Descrição", "descricao", "required",
        editedTema.descricao]]
    radio = ["foto", fotos, editedTema.foto]
    return render_template('showFORM.html', id=id, fields=fields,
                           editing=editedTema, fotos=radio, table="Tema")


@app.route('/tema/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editTema(id):
    fotos = session.query(Foto).all()
    editedTema = session.query(Tema).filter_by(id=id).one()
    if request.method == 'POST':
        if request.form['nome']:
            editedTema.nome = request.form['nome']
        if request.form['descricao']:
            editedTema.descricao = request.form['descricao']
        if request.form['foto']:
            editedTema.foto = request.form['foto']
        session.add(editedTema)
        session.commit()
        return redirect(url_for('listTema'))
    else:
        fields = [["input", "Nome", "nome", "required", editedTema.nome], [
            "textarea", "Descrição", "descricao",
            editedTema.descricao]]
        radio = ["foto", fotos, editedTema.foto]
        return render_template('editFORM.html', id=id, fields=fields,
                               editing=editedTema, fotos=radio, table="Tema")


@app.route('/tema/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteTema(id):
    temaToDelete = session.query(Tema).filter_by(id=id).one()
    if request.method == 'POST':
        session.delete(temaToDelete)
        session.commit()
        return redirect(url_for('listTema'))
    else:
        return render_template('deleteFORM.html', record=temaToDelete,
                               table="Tema")


# ##### OBJETOS ######

@app.route('/objetos')
@login_required
def listObjeto():
    fotos = session.query(Foto).all()
    objetos = session.query(Objeto).all()
    return render_template('listFORM.html', table="Objeto", var_table=objetos,
                           fotos=fotos)


@app.route('/objeto/<int:id>')
@login_required
def showObjeto(id):
    fotos = session.query(Foto).all()
    editedObjeto = session.query(Objeto).filter_by(id=id).one()
    if request.method == 'POST':
        if request.form['nome']:
            editedObjeto.nome = request.form['nome']
        if request.form['descricao']:
            editedObjeto.descricao = request.form['descricao']
        if request.form['foto']:
            editedObjeto.foto = request.form['foto']
        session.add(editedObjeto)
        session.commit()
        return redirect(url_for('listObjeto'))
    else:
        fields = [["input", "Nome", "nome", "required", editedObjeto.nome], [
            "textarea", "Descrição", "descricao", "required",
            editedObjeto.descricao]]
        radio = ["foto", fotos, editedObjeto.foto]
        return render_template('editFORM.html', id=id, fields=fields,
                               editing=editedObjeto, fotos=radio,
                               table="Objeto")


@app.route('/objeto/new', methods=['GET', 'POST'])
@login_required
def newObjeto():
    fotos = session.query(Foto).all()
    if request.method == 'POST':  # response from template form

        newObjeto = Objeto(nome=request.form['nome'], descricao=request.form[
            'descricao'], foto=request.form['foto'])
        session.add(newObjeto)
        session.commit()
        return redirect(url_for('listObjeto'))
    else:
        fields = [["input", "Nome", "nome", "required"],
                  ["textarea", "Descrição", "descricao"]]
        radio = ["foto", fotos]
        return render_template('newFORM.html', fotos=radio, fields=fields,
                               table="Objeto")


@app.route('/objeto/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editObjeto(id):
    fotos = session.query(Foto).all()
    editedObjeto = session.query(Objeto).filter_by(id=id).one()
    if request.method == 'POST':
        if request.form['nome']:
            editedObjeto.nome = request.form['nome']
        if request.form['descricao']:
            editedObjeto.descricao = request.form['descricao']
        if request.form['foto']:
            editedObjeto.foto = request.form['foto']
        session.add(editedObjeto)
        session.commit()
        return redirect(url_for('listObjeto'))
    else:
        fields = [["input", "Nome", "nome", "required", editedObjeto.nome],
                  ["textarea", "Descrição", "descricao",
                   editedObjeto.descricao]]
        radio = ["foto", fotos]
        return render_template('editFORM.html', id=id, fields=fields,
                               editing=editedObjeto, fotos=radio,
                               table="Objeto")


@app.route('/objeto/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteObjeto(id):
    objetoToDelete = session.query(Objeto).filter_by(id=id).one()
    if request.method == 'POST':
        session.delete(objetoToDelete)
        session.commit()
        return redirect(url_for('listObjeto'))
    else:
        return render_template('deleteFORM.html', record=objetoToDelete,
                               table="Objeto")


# ##### FESTA ######
@app.route('/festas')
@login_required
def listFesta():
    fotos = session.query(Foto).all()
    festas = session.query(Festa).all()
    temas = session.query(Tema).all()
    taxonomies = [["select", "Tema", "tema", temas]]
    return render_template('listFORM.html', table="Festa",
                           var_table=festas, fotos=fotos,
                           taxonomies=taxonomies)


@app.route('/festa/<int:id>')
@login_required
def showFesta(id):

    artes = session.query(Arte).all()
    fotos = session.query(Foto).all()
    temas = session.query(Tema).all()
    editedFesta = session.query(Festa).filter_by(id=id).one()
    fields = [["input", "Nome", "nome", "required", editedFesta.nome],
              ["textarea", "Descrição", "descricao", "required",
               editedFesta.descricao], ["input", "Valor", "valor", "",
                                        editedFesta.valor]]
    taxonomies = [["select", "Tema", "tema", temas, editedFesta.tema]]
    radio = ["foto", fotos, editedFesta.foto]
    artes = [["Artes", artes, editedFesta.artes]]
    return render_template('showFORM.html', id=id, fields=fields,
                           editing=editedFesta, fotos=radio,
                           taxonomies=taxonomies,
                           checkboxes=artes, table="Festa")


@app.route('/festa/new', methods=['GET', 'POST'])
@login_required
def newFesta():
    fotos = session.query(Foto).all()
    temas = session.query(Tema).all()
    artes = session.query(Arte).all()
    if request.method == 'POST':  # response from template form
        newFesta = Festa(nome=request.form['nome'],
                         descricao=request.form['descricao'],
                         valor=request.form['price'],
                         foto=request.form['foto'],
                         tema=request.form['tema'])
        # adicionar Artes que essa festa contem
        artes_selected = request.form.getlist('artes')
        for id_arte in artes_selected:
            arte = session.query(Arte).filter_by(id=id_arte).one()
            newFesta.artes.append(arte)
        for arte in newFesta.artes:
            print(arte.id, ".", arte.nome)
        session.add(newFesta)
        session.commit()
        return redirect(url_for('listFesta'))
    else:
        fields = [["input", "Nome", "nome", "required"], ["textarea",
                                                          "Descrição",
                                                          "descricao"],
                  ["input",
                   "Valor",
                   "price"]]
        taxonomies = [["select", "Tema", "tema", temas]]
        radio = ["foto", fotos]
        artes = [["Artes", artes]]
        return render_template('newFORM.html', taxonomies=taxonomies,
                               fields=fields, fotos=radio, checkboxes=artes,
                               table="Festa")


@app.route('/festa/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editFesta(id):
    temas = session.query(Tema).all()
    fotos = session.query(Foto).all()
    artes = session.query(Arte).all()
    editedFesta = session.query(Festa).filter_by(id=id).one()
    if request.method == 'POST':
        if request.form['nome']:
            editedFesta.nome = request.form['nome']
        if request.form['descricao']:
            editedFesta.descricao = request.form['descricao']
        if request.form['tema']:
            editedFesta.tema = request.form['tema']
        if request.form['valor']:
            editedFesta.valor = request.form['valor']
        if request.form['foto']:
            editedFesta.foto = request.form['foto']
        if request.form['artes']:
            artes_selected = request.form.getlist('artes')
            for id_arte in artes_selected:
                arte = session.query(Arte).filter_by(id=id_arte).one()
                editedFesta.artes.append(arte)
        session.add(editedFesta)
        session.commit()
        return redirect(url_for('listFesta'))
    else:
        fields = [["input", "Nome", "nome", "required", editedFesta.nome],
                  ["textarea", "Descrição", "descricao",
                   editedFesta.descricao], ["input", "Valor", "valor", "",
                                            editedFesta.valor]]
        taxonomies = [["select", "Tema", "tema", temas, editedFesta.tema]]
        radio = ["foto", fotos, editedFesta.foto]
        artes = [["Artes", artes, editedFesta.artes]]
        return render_template('editFORM.html', id=id, fields=fields,
                               editing=editedFesta, fotos=radio,
                               taxonomies=taxonomies,
                               checkboxes=artes, table="Festa")


@app.route('/festa/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteFesta(id):
    festaToDelete = session.query(Festa).filter_by(id=id).one()
    if request.method == 'POST':
        session.delete(festaToDelete)
        session.commit()
        return redirect(url_for('listFesta'))
    else:
        return render_template('deleteFORM.html', record=festaToDelete,
                               table="Festa")

# ##### ARTE ######


@app.route('/festas/JSON')
@login_required
def listFestaJSON():
    festas = session.query(Festa).options(joinedload(Festa.artes)).all()
    artes = session.query(Arte).options(joinedload(Arte.prods)).all()
    return jsonify(dict(Festa=[dict(c.serialize,
                                    Artes=[dict(c.serialize,
                                                Produtos=[i.serialize
                                                          for i in c.prods])
                                           for c in artes])
                               for c in festas]))


@app.route('/festa/<int:id>/JSON')
@login_required
def showFestaJSON(id):
    artes = session.query(Arte).options(joinedload(Arte.prods)).all()
    festas = session.query(Festa).options(
        joinedload(Festa.artes)).filter_by(id=id)
    return jsonify(dict(Festa=[dict(c.serialize, Artes=[dict(c.serialize,
                                                             Produtos=[
                                                                 i.serialize
                                                                 for i in
                                                                 c.prods])
                                                        for c in artes])
                               for c in festas]))


@app.route('/artes/JSON')
@login_required
def listArteJSON():
    artes = session.query(Arte).options(joinedload(Arte.prods)).all()
    return jsonify(dict(Artes=[dict(c.serialize, Produtos=[i.serialize
                                                           for i in c.prods])
                               for c in artes]))


@app.route('/produtos/JSON')
@login_required
def listProdutoJSON():
    produtos = session.query(Produto).all()
    return jsonify(produtos=[i.serialize for i in produtos])


@app.route('/temas/JSON')
@login_required
def listTemaJSON():
    temas = session.query(Tema).all()
    return jsonify(temas=[i.serialize for i in temas])


@app.route('/fotos/JSON')
@login_required
def listFotoJSON():
    fotos = session.query(Foto).all()
    return jsonify(fotos=[i.serialize for i in fotos])


@app.route('/artes')
@login_required
def listArte():
    fotos = session.query(Foto).all()
    artes = session.query(Arte).all()
    temas = session.query(Tema).all()
    objetos = session.query(Objeto).all()
    taxonomies = [["select", "Tema", "tema", temas],
                  ["select", "Objeto", "objeto", objetos]]

    return render_template('listFORM.html', table="Arte", var_table=artes,
                           fotos=fotos, taxonomies=taxonomies)


@app.route('/arte/<int:id>')
@login_required
def showArte(id):
    fotos = session.query(Foto).all()
    objetos = session.query(Objeto).all()
    produtos = session.query(Produto).all()
    editedArte = session.query(Arte).filter_by(id=id).one()
    temas = session.query(Tema).all()
    fields = [["input", "Nome", "nome", "required", editedArte.nome],
              ["textarea", "Descrição", "descricao", "", editedArte.descricao]]
    taxonomies = [["select", "Tema", "tema", temas],
                  ["select", "Objeto", "objeto", objetos]]
    radio = ["foto", fotos, editedArte.foto]
    produtos = [["produto", produtos, editedArte.produtos]]
    return render_template('showFORM.html', id=id, fields=fields,
                           editing=editedArte, fotos=radio,
                           taxonomies=taxonomies,
                           checkboxes=produtos, table="Arte")


@app.route('/arte/new', methods=['GET', 'POST'])
@login_required
def newArte():
    fotos = session.query(Foto).all()
    temas = session.query(Tema).all()
    produtos = session.query(Produto).all()
    objetos = session.query(Objeto).all()
    if request.method == 'POST':  # response from template form
        newArte = Arte(nome=request.form['nome'],
                       descricao=request.form['descricao'],
                       foto=request.form['foto'],
                       tema=request.form['tema'],
                       objeto=request.form['objeto'])

        produtos_selected = request.form.getlist('produtos')
        for id_produto in produtos_selected:
            produto = session.query(Produto).filter_by(id=id_produto).one()
            newArte.produtos.append(produto)
        session.add(newArte)
        session.commit()
        return redirect(url_for('listArte'))
    else:
        fields = [["input", "Nome", "nome", "required"],
                  ["textarea", "Descrição", "descricao"]]
        taxonomies = [["select", "Tema", "tema", temas],
                      ["select", "Objeto", "objeto", objetos]]
        radio = ["foto", fotos]
        produtos = [["produtos", produtos]]
        return render_template('newFORM.html', taxonomies=taxonomies,
                               fields=fields, fotos=radio,
                               checkboxes=produtos,
                               table="Arte")


@app.route('/arte/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editArte(id):
    temas = session.query(Tema).all()
    fotos = session.query(Foto).all()
    produtos = session.query(Produto).all()
    objetos = session.query(Objeto).all()
    editedArte = session.query(Arte).filter_by(id=id).one()
    if request.method == 'POST':
        if request.form['nome']:
            editedArte.nome = request.form['nome']
        if request.form['descricao']:
            editedArte.descricao = request.form['descricao']
        if request.form['tema']:
            editedArte.tema = request.form['tema']
        if request.form['objeto']:
            editedArte.valor = request.form['objeto']
        if request.form['foto']:
            editedArte.foto = request.form['foto']
        if request.form['produtos']:
            produtos_selected = request.form.getlist('produtos')
            for id_produto in produtos_selected:
                produto = session.query(Produto).filter_by(id=id_produto).one()
                editedArte.produtos.append(produto)
        session.add(editedArte)
        session.commit()
        return redirect(url_for('listArte'))
    else:
        fields = [["input", "Nome", "nome", "required", editedArte.nome],
                  ["textarea", "Descrição", "descricao", editedArte.descricao]]
        taxonomies = [["select", "Tema", "tema", temas],
                      ["select", "Objeto", "objeto", objetos]]
        radio = ["foto", fotos, editedArte.foto]
        produtos = [["produtos", produtos, editedArte.produtos]]
        return render_template('editFORM.html', id=id, fields=fields,
                               editing=editedArte, fotos=radio,
                               taxonomies=taxonomies,
                               checkboxes=produtos, table="Arte")


@app.route('/arte/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteArte(id):
    arteToDelete = session.query(Arte).filter_by(id=id).one()
    if request.method == 'POST':
        session.delete(arteToDelete)
        session.commit()
        return redirect(url_for('listArte'))
    else:
        return render_template('deleteFORM.html', table="Arte", var="arte",
                               record=arteToDelete)


if __name__ == '__main__':
    app.secret_key = ''.join(random.choice(
        string.ascii_uppercase + string.digits) for x in range(32))
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
