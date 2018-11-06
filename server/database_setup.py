#!/usr/local/bin/python3
# encoding=utf8
import os
import sys
from sqlalchemy import Table, Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()  # classses especiais que correspondem a tabelas

engine = create_engine('postgresql://catalog:clipper02@localhost/catalog')

artes_festa = Table('itens', Base.metadata,
                    Column('festa_id', Integer, ForeignKey('festa.id')),
                    Column('arte_id', Integer, ForeignKey('arte.id'))
                    )
produtos_arte = Table('prods', Base.metadata,
                      Column('arte_id', Integer, ForeignKey('arte.id')),
                      Column('produto_id', Integer, ForeignKey('produto.id'))
                      )


class Festa(Base):
    '''Festa e uma tabela que registra um conjunto de informacões
    e pode ser considerada principalmente um conjunto de artes'''
    __tablename__ = 'festa'
    id = Column('id', Integer, primary_key=True, nullable=False)
    nome = Column('nome', String(255), nullable=False)
    descricao = Column('descricao', String(255), nullable=False)
    valor = Column('valor', Integer, nullable=False)
    foto = Column('foto', Integer, ForeignKey('foto.id'))
    tema = Column('tema', Integer, ForeignKey('tema.id'))
    user = Column('user', Integer, ForeignKey('user.id'))


    user_festa = relationship('User', foreign_keys=user)
    artes = relationship('Arte', secondary=artes_festa)
    foto_festa = relationship('Foto', foreign_keys=foto)
    tema_festa = relationship('Tema', foreign_keys=tema)

    @property
    def serialize(self):
        return{
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'valor': self.valor,
            'foto': self.foto,
            'tema': self.tema
        }


class Arte(Base):
    '''Artes e a tabela de registros que contem um conjunto
     de produtos e informacões referentes a um desenho distinto
     dos outros'''
    __tablename__ = 'arte'
    id = Column('id', Integer, primary_key=True, nullable=False)
    nome = Column('nome', String(255),  nullable=False)
    descricao = Column('descricao', String(255),  nullable=False)
    foto = Column(
        'foto', Integer, ForeignKey('foto.id'))
    objeto = Column('objeto', Integer, ForeignKey('objeto.id'))
    tema = Column('tema', Integer, ForeignKey('tema.id'))
    user = Column('user', Integer, ForeignKey('user.id'))


    user_arte = relationship('User', foreign_keys=user)
    tema_arte = relationship('Tema', foreign_keys=tema)
    objeto_arte = relationship('Objeto', foreign_keys=objeto)
    foto_arte = relationship('Foto', foreign_keys=foto)
    produtos = relationship(
        'Produto', secondary=produtos_arte, backref='artes')

    @property
    def serialize(self):
        return{
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'objeto': self.objeto,
            'foto': self.foto,
            'tema': self.tema
        }


class Produto(Base):
    '''Produto e uma tabela que cadastra
    os arquivos das artes que serao comercializados ou outros tipos
    de Produto. Cada produto esta relacionado à uma arte.'''
    __tablename__ = 'produto'
    id = Column('id', Integer, primary_key=True, nullable=False)
    caminho = Column('caminho', String(255))
    descricao = Column('descricao', String(255))
    valor = Column('valor', Integer)
    arte = Column('arte', Integer, ForeignKey('arte.id'))
    user = Column('user', Integer, ForeignKey('user.id'))


    user_produto = relationship('User', foreign_keys=user)
    arte_produto = relationship(
        'Arte', foreign_keys=arte, backref='prods')

    @property
    def serialize(self):
        return{
            'id': self.id,
            'caminho': self.caminho,
            'descricao': self.descricao,
            'valor': self.valor,
            'arte': self.arte
        }


class User(Base):
    '''Tabela de usuarios'''
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    picture = Column(String(255), unique=True, nullable=False)

    @property
    def serialize(self):
        return{
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'picture': self.picture
        }


class Foto(Base):
    '''Tabela com as fotografias utilizadas nas outras tabelas'''
    __tablename__ = 'foto'
    id = Column('id', Integer, primary_key=True, nullable=False)
    descricao = Column('descricao', String(255))
    caminho = Column('caminho', String(255))
    user = Column('user', Integer, ForeignKey('user.id'))


    user_foto = relationship('User', foreign_keys=user)
    @property
    def serialize(self):
        return{
            'id': self.id,
            'descricao': self.descricao,
            'caminho': self.caminho
        }


class Tema(Base):
    '''Tabela com os temas que classificam as artes e festas'''
    __tablename__ = 'tema'
    id = Column('id', Integer, primary_key=True, nullable=False)
    nome = Column('nome', String(255))
    descricao = Column('descricao', String(255))
    foto = Column(
        'foto', Integer, ForeignKey('foto.id'))
    user = Column('user', Integer, ForeignKey('user.id'))


    user_tema = relationship('User', foreign_keys=user)
    foto_tema = relationship('Foto', foreign_keys=foto)

    @property
    def serialize(self):
        return{
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'foto': self.foto,
        }


class Objeto(Base):
    ''' Tipos de objetos em que as artes podem ser classificadas.
    Cestas, tops e Balões por exemplo'''
    __tablename__ = 'objeto'
    id = Column('id', Integer, primary_key=True, nullable=False)
    nome = Column('nome', String(255))
    descricao = Column('descricao', String(255))
    foto = Column(
        'foto', Integer, ForeignKey('foto.id'))
    user = Column('user', Integer, ForeignKey('user.id'))


    user_objeto = relationship('User', foreign_keys=user)
    foto_objeto = relationship('Foto', foreign_keys=foto)

    @property
    def serialize(self):
        return{
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'foto': self.foto,
        }


Base.metadata.create_all(engine)
