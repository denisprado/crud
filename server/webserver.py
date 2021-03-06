#!/usr/local/bin/python
# encoding=utf8
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
    '''Verifique se o usuario esta logado '''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            return redirect(url_for('showLogin'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    ''' Verifique se a extensao do arquivo enviado e permitida '''
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/login')
def showLogin():
    ''' Crie uma variavel de estado e redirecione para pagina de login'''
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state, client_id=CLIENT_ID)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    ''' Conecte o usuario atraves do Google Plus '''
    # Validate state token
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
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Usuario ja conectado.'),
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
    print(data)
    if 'name' in login_session:
        login_session['username'] = data['name']
    else:
        login_session['username'] = data['email']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # verifica e cria conta se ele n existir
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h2>Bem vindo, '
    output += login_session['username']
    output += '!</h2>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 150px;height:150px;'
    output += 'border-radius: 50%;object-fit:cover;">'
    flash("you are now logged in as %s" % login_session['username'])
    return output


# User Helper Functions
def createUser(login_session):
    '''Crie o usuario utilizando informacões do Google Plus'''
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    '''Localize o item do usuario a partir do ID fornecido'''
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    ''' Retorne o ID do usuario a partir do email fornecido'''
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except ValueError:
        return None


@app.route('/gdisconnect')
def gdisconnect():
    '''Desconecte o usuario'''
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url_initial = 'https://accounts.google.com/o/oauth2/revoke?'
    url = url_initial + 'token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
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
@login_required
def index():
    ''' Redirecione para a pagina de listagem de artes '''
    return redirect(url_for('listArte'))


@app.route('/produto/<filename>')
@app.route('/foto/<filename>')
@login_required
def uploaded_file(filename):
    ''' Retorne o caminho da imagem a partir do nome fornecido'''
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/fotos')
@login_required
def listFoto():
    '''Liste as fotos cadastradas'''
    fotos = session.query(Foto).all()
    fields = [["input", "Nome", "nome", "required"], [
        "textarea", "Descricao", "descricao", "required"]]
    return render_template('listFORM.html', fields=fields, fotos=fotos,
                           table="Foto", var_table=fotos)


@app.route('/foto/<int:id>',
           methods=['GET', 'POST'])
@login_required
def showFoto(id):
    '''Mostre uma foto a partir do id fornecido'''
    editedItem = session.query(Foto).filter_by(id=id).one()
    fields = [["textarea", "Descricao", "descricao", "required",
               editedItem.descricao], ["file", "Arquivo", "file", "required",
                                       editedItem.caminho]]
    return render_template('showFORM.html', id=id, fields=fields,
                           editing=editedItem, table="Foto")


@app.route('/foto/new', methods=['POST', 'GET'])
@login_required
def newFoto():
    '''Crie um item de foto'''
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
                           descricao=request.form['descricao'],
                           user=login_session['user_id'])
            session.add(newFoto)
            session.commit()
            return redirect(url_for('listFoto'))
    fields = [["file", "Arquivo", "file", "required"], [
        "textarea", "Descricao", "descricao", "required"]]
    return render_template('newFORM.html', fields=fields, table="Foto")


@app.route('/foto/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editFoto(id):
    ''' Edite uma fotografia a partir de ID fornecido'''
    editedItem = session.query(Foto).filter_by(id=id).one()
    if editedItem.user == login_session['user_id']:
        if request.method == 'POST':
            file = request.files['file']
            # Se foi carregado arquivo
            if file:
                filename = secure_filename(file.filename)
                editedItem.caminho = filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                session.add(editedItem)
                session.commit()
                flash("Nova foto adicionada")
            if request.form['descricao']:
                editedItem.descricao = request.form['descricao']
                editedItem.user = login_session['user_id']
            return redirect(url_for('listFoto'))
        else:
            fields = [["textarea", "Descricao", "descricao",
                       editedItem.descricao], ["file", "Arquivo", "file",
                                               "required", editedItem.caminho]]
            return render_template('editFORM.html', id=id, fields=fields,
                                   editing=editedItem, table="Foto")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listFoto'))


@app.route('/foto/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteFoto(id):
    '''Delete um item de fotografia e o seu respectivo arquivo'''
    fotoToDelete = session.query(Foto).filter_by(id=id).one()
    if fotoToDelete.user == login_session['user_id']:
        if request.method == 'POST':
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], url_for(
                'uploaded_file', filename=fotoToDelete.caminho)))
            session.delete(fotoToDelete)
            session.commit()
            return redirect(url_for('listFoto'))
        else:
            return render_template('deleteFORM.html', record=fotoToDelete,
                                   table="Foto")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listFoto'))


@app.route('/produtos')
@login_required
def listProduto():
    '''Liste os produtos (arquivos digitais) cadastrados'''
    produtos = session.query(Produto).all()
    fields = [["input", "Descricao", "descricao",
               "required"], ["input", "Valor", "valor", "required"]]
    return render_template('listFORM.html', table="Produto",
                           var_table=produtos, fields=fields)


@app.route('/produto/new', methods=['POST', 'GET'])
@login_required
def newProduto():
    ''' Crie um novo produto (arquivo digital de arte)'''
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
                valor=request.form['valor'],
                user=login_session['user_id'])
            session.add(newProduto)
            session.commit()
            return redirect(url_for('listProduto'))
    fields = [["file", "Arquivo", "file", "required"], [
        "textarea", "Descricao", "descricao"], ["input", "Valor", "valor",
                                                "required"]]
    return render_template('newFORM.html', fields=fields, table="Produto")


@app.route('/produto/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editProduto(id):
    '''Edite um produto'''
    editedItem = session.query(Produto).filter_by(id=id).one()
    if editedItem.user == login_session['user_id']:
        if request.method == 'POST':
            file = request.files['file']
            if file:
                filename = secure_filename(file.filename)
                editedItem.caminho = filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                editedItem.user = login_session['user_id']
                session.add(editedItem)
                session.commit()
                return redirect(url_for('listProduto'))
        else:
            fields = [["file", "Arquivo", "file", "required",
                       editedItem.caminho], ["textarea", "Descricao",
                                             "descricao",
                                             editedItem.descricao],
                      ["input", "Valor", "valor", "", editedItem.valor]]
            return render_template('editFORM.html', id=id,
                                   fields=fields, editing=editedItem,
                                   table="Produto")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listProduto'))


@app.route('/produto/<int:id>',
           methods=['GET', 'POST'])
@login_required
def showProduto(id):
    '''Mostre os produtos (arquivos digitais de arte) cadastrados'''
    editedItem = session.query(Produto).filter_by(id=id).one()
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            editedItem.caminho = filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            session.add(editedItem)
            session.commit()
            return redirect(url_for('listProduto'))
    else:
        fields = [["textarea", "Descricao", "descricao", "required",
                   editedItem.descricao], [
            "input", "Valor", "valor", "", editedItem.valor]]
        return render_template('showFORM.html', id=id, fields=fields,
                               editing=editedItem, table="Produto")


@app.route('/produto/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteProduto(id):
    '''Delete um produto a partir de um ID fornecido'''
    produtoToDelete = session.query(Produto).filter_by(id=id).one()

    if request.method == 'POST':
        session.delete(produtoToDelete)
        session.commit()
        return redirect(url_for('listProduto'))
    else:
        return render_template('deleteFORM.html', record=produtoToDelete,
                               table="Produto")


@app.route('/temas')
@login_required
def listTema():
    '''Liste os temas registrados'''
    fotos = session.query(Foto).all()
    temas = session.query(Tema).all()
    fields = [["input", "Nome", "nome", "required"], [
        "textarea", "Descricao", "descricao", "required"]]
    return render_template('listFORM.html', id=id, fields=fields, fotos=fotos,
                           table="Tema", var_table=temas)


@app.route('/tema/new', methods=['GET', 'POST'])
@login_required
def newTema():
    '''Crie um novo tema para as artes e festas'''
    fotos = session.query(Foto).all()
    if request.method == 'POST':  # response from template form
        newTema = Tema(nome=request.form['nome'], descricao=request.form[
            'descricao'], foto=request.form['foto'])
        session.add(newTema)
        session.commit()
        return redirect(url_for('listTema'))
    else:
        fields = [["input", "Nome", "nome", "required"],
                  ["textarea", "Descricao", "descricao"]]
        radio = ["foto", fotos]
        return render_template('newFORM.html', fotos=radio, fields=fields,
                               table="Tema", user=login_session['user_id'])


@app.route('/tema/<int:id>',
           methods=['GET', 'POST'])
@login_required
def showTema(id):
    '''Mostre os temas cadastrados'''
    fotos = session.query(Foto).all()
    editedItem = session.query(Tema).filter_by(id=id).one()
    fields = [["input", "Nome", "nome", "required", editedItem.nome], [
        "textarea", "Descricao", "descricao", "required",
        editedItem.descricao]]
    radio = ["foto", fotos, editedItem.foto]
    return render_template('showFORM.html', id=id, fields=fields,
                           editing=editedItem, fotos=radio, table="Tema")


@app.route('/tema/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editTema(id):
    '''Edite um tema a partir de uma ID fornecido'''
    fotos = session.query(Foto).all()
    editedItem = session.query(Tema).filter_by(id=id).one()
    if editedItem.user == login_session['user_id']:
        if request.method == 'POST':
            if request.form['nome']:
                editedItem.nome = request.form['nome']
            if request.form['descricao']:
                editedItem.descricao = request.form['descricao']
            if request.form['foto']:
                editedItem.foto = request.form['foto']
            editedItem.user = login_session['user_id']
            session.add(editedItem)
            session.commit()
            return redirect(url_for('listTema'))
        else:
            fields = [["input", "Nome", "nome", "required", editedItem.nome], [
                "textarea", "Descricao", "descricao",
                editedItem.descricao]]
            radio = ["foto", fotos, editedItem.foto]
            return render_template('editFORM.html', id=id, fields=fields,
                                   editing=editedItem, fotos=radio,
                                   table="Tema")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listTema'))


@app.route('/tema/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteTema(id):
    '''Delete um tema cadastrado a partir de um ID fornecido'''
    temaToDelete = session.query(Tema).filter_by(id=id).one()
    if temaToDelete.user == login_session['user_id']:
        if request.method == 'POST':
            session.delete(temaToDelete)
            session.commit()
            return redirect(url_for('listTema'))
        else:
            return render_template('deleteFORM.html', record=temaToDelete,
                                   table="Tema")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listTema'))


@app.route('/objetos')
@login_required
def listObjeto():
    '''Lista os objetos cadastrados'''
    fotos = session.query(Foto).all()
    objetos = session.query(Objeto).all()
    return render_template('listFORM.html', table="Objeto", var_table=objetos,
                           fotos=fotos)


@app.route('/objeto/<int:id>')
@login_required
def showObjeto(id):
    '''Mostre um Objeto a partir de um ID fornecido'''
    fotos = session.query(Foto).all()
    editedItem = session.query(Objeto).filter_by(id=id).one()
    if request.method == 'POST':
        if request.form['nome']:
            editedItem.nome = request.form['nome']
        if request.form['descricao']:
            editedItem.descricao = request.form['descricao']
        if request.form['foto']:
            editedItem.foto = request.form['foto']
        session.add(editedItem)
        session.commit()
        return redirect(url_for('listObjeto'))
    else:
        fields = [["input", "Nome", "nome", "required", editedItem.nome], [
            "textarea", "Descricao", "descricao", "required",
            editedItem.descricao]]
        radio = ["foto", fotos, editedItem.foto]
        return render_template('editFORM.html', id=id, fields=fields,
                               editing=editedItem, fotos=radio,
                               table="Objeto")


@app.route('/objeto/new', methods=['GET', 'POST'])
@login_required
def newObjeto():
    '''Cria um novo objeto de Arte'''
    fotos = session.query(Foto).all()
    if request.method == 'POST':  # response from template form

        newObjeto = Objeto(nome=request.form['nome'], descricao=request.form[
            'descricao'], foto=request.form['foto'],
            user=login_session['user_id'])
        session.add(newObjeto)
        session.commit()
        return redirect(url_for('listObjeto'))
    else:
        fields = [["input", "Nome", "nome", "required"],
                  ["textarea", "Descricao", "descricao"]]
        radio = ["foto", fotos]
        return render_template('newFORM.html', fotos=radio, fields=fields,
                               table="Objeto")


@app.route('/objeto/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editObjeto(id):
    '''Edita um objeto'''
    fotos = session.query(Foto).all()
    editedItem = session.query(Objeto).filter_by(id=id).one()
    if editedItem.user == login_session['user_id']:
        if request.method == 'POST':
            if request.form['nome']:
                editedItem.nome = request.form['nome']
            if request.form['descricao']:
                editedItem.descricao = request.form['descricao']
            if request.form['foto']:
                editedItem.foto = request.form['foto']
            editedItem.user = login_session['user_id']
            session.add(editedItem)
            session.commit()
            return redirect(url_for('listObjeto'))
        else:
            fields = [["input", "Nome", "nome", "required", editedItem.nome],
                      ["textarea", "Descricao", "descricao",
                       editedItem.descricao]]
            radio = ["foto", fotos]
            return render_template('editFORM.html', id=id, fields=fields,
                                   editing=editedItem, fotos=radio,
                                   table="Objeto")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listObjeto'))


@app.route('/objeto/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteObjeto(id):
    '''Apaga o objeto a partir de um ID fornecido'''
    objetoToDelete = session.query(Objeto).filter_by(id=id).one()
    if objetoToDelete.user == login_session['user_id']:
        if request.method == 'POST':
            session.delete(objetoToDelete)
            session.commit()
            return redirect(url_for('listObjeto'))
        else:
            return render_template('deleteFORM.html', record=objetoToDelete,
                                   table="Objeto")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listObjeto'))


@app.route('/festas')
@login_required
def listFesta():
    '''Lista as festas cadastradas'''
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
    '''Mostre uma festa cadastrada'''
    artes = session.query(Arte).all()
    fotos = session.query(Foto).all()
    temas = session.query(Tema).all()
    editedItem = session.query(Festa).filter_by(id=id).one()
    fields = [["input", "Nome", "nome", "required", editedItem.nome],
              ["textarea", "Descricao", "descricao", "required",
               editedItem.descricao], ["input", "Valor", "valor", "",
                                       editedItem.valor]]
    taxonomies = [["select", "Tema", "tema", temas, editedItem.tema]]
    radio = ["foto", fotos, editedItem.foto]
    artes = [["artes", artes, editedItem.artes]]
    return render_template('showFORM.html', id=id, fields=fields,
                           editing=editedItem, fotos=radio,
                           taxonomies=taxonomies,
                           checkboxes=artes, table="Festa")


@app.route('/festa/new', methods=['GET', 'POST'])
@login_required
def newFesta():
    '''Cria uma nova festa'''
    fotos = session.query(Foto).all()
    temas = session.query(Tema).all()
    artes = session.query(Arte).all()
    if request.method == 'POST':  # response from template form
        newFesta = Festa(nome=request.form['nome'],
                         descricao=request.form['descricao'],
                         valor=request.form['price'],
                         foto=request.form['foto'],
                         tema=request.form['tema'],
                         user=login_session['user_id'])
        # adicionar Artes que essa festa contem
        artes_selected = request.form.getlist('artes')
        for id_arte in artes_selected:
            arte = session.query(Arte).filter_by(id=id_arte).one()
            newFesta.artes.append(arte)
        session.add(newFesta)
        session.commit()
        return redirect(url_for('listFesta'))
    else:
        fields = [["input", "Nome", "nome", "required"], ["textarea",
                                                          "Descricao",
                                                          "descricao"],
                  ["input",
                   "Valor",
                   "price"]]
        taxonomies = [["select", "Tema", "tema", temas]]
        radio = ["foto", fotos]
        artes = [["artes", artes]]
        return render_template('newFORM.html', taxonomies=taxonomies,
                               fields=fields, fotos=radio, checkboxes=artes,
                               table="Festa")


@app.route('/festa/<int:id>/edit',
           methods=['GET', 'POST'])
@login_required
def editFesta(id):
    '''edita uma nova festa'''
    temas = session.query(Tema).all()
    fotos = session.query(Foto).all()
    artes = session.query(Arte).all()
    editedItem = session.query(Festa).filter_by(id=id).one()

    if editedItem.user == login_session['user_id']:
        if request.method == 'POST':
            if request.form['nome']:
                editedItem.nome = request.form['nome']
            if request.form['descricao']:
                editedItem.descricao = request.form['descricao']
            if request.form['tema']:
                editedItem.tema = request.form['tema']
            if request.form['valor']:
                editedItem.valor = request.form['valor']
            if request.form['foto']:
                editedItem.foto = request.form['foto']
            if request.form['artes']:
                artes_selected = request.form.getlist('artes')
                editedItem.artes = []
                for id_arte in artes_selected:
                    arte = session.query(Arte).filter_by(id=id_arte).one()
                    editedItem.artes.append(arte)
            editedItem.user = login_session['user_id']
            session.add(editedItem)
            session.commit()
            return redirect(url_for('listFesta'))
        else:
            fields = [["input", "Nome", "nome", "required", editedItem.nome],
                      ["textarea", "Descricao", "descricao",
                       editedItem.descricao], ["input", "Valor", "valor", "",
                                               editedItem.valor]]
            taxonomies = [["select", "Tema", "tema", temas, editedItem.tema]]
            radio = ["foto", fotos, editedItem.foto]
            artes = [["artes", artes, editedItem.artes]]
            return render_template('editFORM.html', id=id, fields=fields,
                                   editing=editedItem, fotos=radio,
                                   taxonomies=taxonomies,
                                   checkboxes=artes, table="Festa")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listFesta'))


@app.route('/festa/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteFesta(id):
    '''Deleta uma festa'''
    festaToDelete = session.query(Festa).filter_by(id=id).one()
    if festaToDelete.user == login_session['user_id']:
        if request.method == 'POST':
            session.delete(festaToDelete)
            session.commit()
            return redirect(url_for('listFesta'))
        else:
            return render_template('deleteFORM.html', record=festaToDelete,
                                   table="Festa")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listFesta'))


@app.route('/festas/JSON')
@login_required
def listFestaJSON():
    """Liste as festas em formato JSON"""
    festas = session.query(Festa).options(joinedload(Festa.artes)).all()
    artes = session.query(Arte).options(joinedload(Arte.produtos)).all()
    return jsonify(dict(Festa=[dict(c.serialize,
                                    Artes=[dict(c.serialize,
                                                Produtos=[i.serialize
                                                          for i in c.produtos])
                                           for c in artes])
                               for c in festas]))


@app.route('/festa/<int:id>/JSON')
@login_required
def showFestaJSON(id):
    '''Mostre uma festa em formato JSON'''
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


@app.route('/arte/<int:id>/JSON')
@login_required
def showArteJSON(id):
    '''Mostre uma arte em formato JSON'''
    artes = session.query(Arte).options(joinedload(Arte.produtos)).filter_by(
        id=id)
    return jsonify(Arte=[dict(d.serialize,
                              Produtos=[i.serialize
                                        for i in d.produtos])
                         for d in artes])


@app.route('/artes/JSON')
@login_required
def listArteJSON():
    '''Liste as Artes em formato JSON'''
    artes = session.query(Arte).options(joinedload(Arte.produtos)).all()
    return jsonify(dict(Arte=[dict(d.serialize,
                                   Produtos=[i.serialize
                                             for i in d.produtos])
                              for d in artes]))


@app.route('/produtos/JSON')
@login_required
def listProdutoJSON():
    '''Liste os Produtos em formato JSON'''
    produtos = session.query(Produto).all()
    return jsonify(produtos=[i.serialize for i in produtos])


@app.route('/produto/<int:id>/JSON')
@login_required
def showProdutoJSON(id):
    '''Mostre um produto em formato JSON'''
    produto = session.query(Produto).filter_by(id=id)
    return jsonify(produto=[i.serialize for i in produto])


@app.route('/temas/JSON')
@login_required
def listTemaJSON():
    '''Liste os temas em formato JSON'''
    temas = session.query(Tema).all()
    return jsonify(temas=[i.serialize for i in temas])


@app.route('/tema/<int:id>/JSON')
@login_required
def showTemaJSON(id):
    '''Mostre um tema em formato JSON'''
    tema = session.query(Tema).filter_by(id=id)
    return jsonify(tema=[i.serialize for i in tema])


@app.route('/fotos/JSON')
@login_required
def listFotoJSON():
    """Mostre as fotos em formato JSON"""
    fotos = session.query(Foto).all()
    return jsonify(fotos=[i.serialize for i in fotos])


@app.route('/foto/<int:id>/JSON')
@login_required
def showFotoJSON(id):
    '''Mostre as fotos em formato JSON'''
    foto = session.query(Foto).all()
    return jsonify(foto=[i.serialize for i in foto])


@app.route('/objetos/JSON')
@login_required
def listObjetoJSON():
    '''Mostre os objetos em formato JSON'''
    objetos = session.query(Objeto).all()
    return jsonify(objetos=[i.serialize for i in objetos])


@app.route('/objeto/<int:id>/JSON')
@login_required
def showObjetoJSON(id):
    '''Mostre um objeto em formato JSON'''
    objeto = session.query(Objeto).all()
    return jsonify(objeto=[i.serialize for i in objeto])


@app.route('/artes')
@login_required
def listArte():
    '''Mostre as artes cadastradas'''
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
    '''Mostre uma arte a partir de um ID cadastrado'''
    fotos = session.query(Foto).all()
    objetos = session.query(Objeto).all()
    produtos = session.query(Produto).all()
    editedItem = session.query(Arte).filter_by(id=id).one()
    temas = session.query(Tema).all()
    fields = [["input", "Nome", "nome", "required", editedItem.nome],
              ["textarea", "Descricao", "descricao", "", editedItem.descricao]]
    taxonomies = [["select", "Tema", "tema", temas],
                  ["select", "Objeto", "objeto", objetos]]
    radio = ["foto", fotos, editedItem.foto]
    produtos = [["produto", produtos, editedItem.produtos]]
    return render_template('showFORM.html', id=id, fields=fields,
                           editing=editedItem, fotos=radio,
                           taxonomies=taxonomies,
                           checkboxes=produtos, table="Arte")


@app.route('/arte/new', methods=['GET', 'POST'])
@login_required
def newArte():
    '''Crie uma nova arte'''
    fotos = session.query(Foto).all()
    temas = session.query(Tema).all()
    produtos = session.query(Produto).all()
    objetos = session.query(Objeto).all()
    if request.method == 'POST':  # response from template form
        newArte = Arte(nome=request.form['nome'],
                       descricao=request.form['descricao'],
                       foto=request.form['foto'],
                       tema=request.form['tema'],
                       objeto=request.form['objeto'],
                       user=login_session['user_id'])

        produtos_selected = request.form.getlist('produtos')
        for id_produto in produtos_selected:
            produto = session.query(Produto).filter_by(id=id_produto).one()
            newArte.produtos.append(produto)
        session.add(newArte)
        session.commit()
        return redirect(url_for('listArte'))
    else:
        fields = [["input", "Nome", "nome", "required"],
                  ["textarea", "Descricao", "descricao"]]
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
    '''Edite uma arte'''
    temas = session.query(Tema).all()
    fotos = session.query(Foto).all()
    produtos = session.query(Produto).all()
    objetos = session.query(Objeto).all()
    editedItem = session.query(Arte).filter_by(id=id).one()
    if editedItem.user == login_session['user_id']:
        if request.method == 'POST':
            if request.form['nome']:
                editedItem.nome = request.form['nome']
            if request.form['descricao']:
                editedItem.descricao = request.form['descricao']
            if request.form['tema']:
                editedItem.tema = request.form['tema']
            if request.form['objeto']:
                editedItem.valor = request.form['objeto']
            if request.form['foto']:
                editedItem.foto = request.form['foto']
            if request.form['produtos']:
                editedItem.produtos = []
                produtos_selected = request.form.getlist('produtos')
                for id_produto in produtos_selected:
                    produto = session.query(
                        Produto).filter_by(id=id_produto).one()
                    editedItem.produtos.append(produto)
            editedItem.user = login_session['user_id']

            session.add(editedItem)
            session.commit()
            return redirect(url_for('listArte'))
        else:
            fields = [["input", "Nome", "nome", "required", editedItem.nome],
                      ["textarea", "Descricao", "descricao",
                       editedItem.descricao]]
            taxonomies = [["select", "Tema", "tema", temas],
                          ["select", "Objeto", "objeto", objetos]]
            radio = ["foto", fotos, editedItem.foto]
            produtos = [["produtos", produtos, editedItem.produtos]]
            return render_template('editFORM.html', id=id, fields=fields,
                                   editing=editedItem, fotos=radio,
                                   taxonomies=taxonomies,
                                   checkboxes=produtos, table="Arte")
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listArte'))


@app.route('/arte/<int:id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteArte(id):
    '''Delete uma arte a partir de um ID fornecido'''
    arteToDelete = session.query(Arte).filter_by(id=id).one()
    if arteToDelete.user == login_session['user_id']:
        if request.method == 'POST':
            session.delete(arteToDelete)
            session.commit()
            return redirect(url_for('listArte'))
        else:
            return render_template('deleteFORM.html', table="Arte", var="arte",
                                   record=arteToDelete)
    else:
        flash("Voce nao tem privilegios para editar este item")
        return redirect(url_for('listArte'))


if __name__ == '__main__':
    app.secret_key = ''.join(random.choice(
        string.ascii_uppercase + string.digits) for x in range(32))
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
