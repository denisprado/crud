# Festa de Papel - Catalogo de Produtos

## Apresentacao
Este e um aplicativo em Python para criacao do catalogo de produtos da loja Festa de Papel que comercializara arquivos de artes para impressoras de corte. O catalogo contem tabelas para gerencimaneto de Festas, de Artes e de Produtos (arquivos digitais). Alem disso, o aplicativo gerencia fotos, temas e (tipos de) objetos que sao utilizados nas tabelas anteriomente. 

Este e um projeto para o Udacity Nanodegree, mas busquei iniciar a solucao de um caso real, que podera ser desenvolvido ate se tornar um aplicativo em producao.

## Relacionamentos entre as Tabelas
O aplicativo foi criado de maneira que as tabelas se relacionam para formar um catalogo. Uma Festa pode conter diversas Artes. Uma Arte pode estar contida em diversas Festas, e contem diversos Produtos (arquivos digitais).  Os Produtos serao listados nos formularios de criacao, edicao e exibicao das Artes, assim como as Artes nos formularios das Festas. As fotos sao centralizadas em uma única tabela onde podem ser enviadas e, posteriormente, ficarao disponíveis para utilizacao como fotos em destaque de Festsa, Artes, Temas e Objetos. Artes e Festas sao relacionadas à Temas. Artes sao relacionadas Objetos (tipo de objeto que a arte e). 

## Início e login
Para iniciar o catalogo, na pasta server, execute 

    python webserver.py
    
Sera necessario se conectar utilizando o Google+ para ter acesso ao gerenciamento dos registros.