import os
import string
import tempfile
from flask import Flask, flash, render_template, request, redirect, url_for, jsonify, send_from_directory
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Foto, Tema, Arte, Festa, Produto, Objeto, tipoProduto, User
from werkzeug.utils import secure_filename
from flask import session as login_session
import random, string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

engine = create_engine('sqlite:///festas_de_papel.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

for i in range(10):
    festa = Festa("Festa "+i, "Uma descricao "+i, ''.join(random(string.digits), i, i))
    session.add(festa)
    session.commit()

for i in range(10):
    arte = Arte("Arte "+i, "Uma descricao "+i, ''.join(random(string.digits), i, i))
    session.add(festa)
    session.commit()

    caminho = Column('caminho', String(255))
    arte = Column('arte', Integer, ForeignKey('arte.id'))
    
    arte_foto = relationship('Arte', foreign_keys=arte)
