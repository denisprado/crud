# Festa de Papel - Catálogo de Produtos

## Apresentação
Este é um aplicativo em Python para criação do catálogo de produtos da loja Festa de Papel que comercializará arquivos de artes para impressoras de corte. O catálogo contém tabelas para gerencimaneto de Festas, de Artes e de Produtos (arquivos digitais). Além disso, o aplicativo gerencia fotos, temas e (tipos de) objetos que são utilizados nas tabelas anteriomente. 

Este é um projeto para o Udacity Nanodegree, mas busquei iniciar a solução de um caso real, que poderá ser desenvolvido até se tornar um aplicativo em produção.

## Relacionamentos entre as Tabelas
O aplicativo foi criado de maneira que as tabelas se relacionam para formar um catálogo. Uma Festa pode conter diversas Artes. Uma Arte pode estar contida em diversas Festas, e contém diversos Produtos (arquivos digitais).  Os Produtos serão listados nos formulários de criação, edição e exibição das Artes, assim como as Artes nos formulários das Festas. As fotos são centralizadas em uma única tabela onde podem ser enviadas e, posteriormente, ficarão disponíveis para utilização como fotos em destaque de Festsa, Artes, Temas e Objetos. Artes e Festas são relacionadas à Temas. Artes são relacionadas Objetos (tipo de objeto que a arte é). 

## Início e login
Para iniciar o catálogo, na pasta server, execute 

    python webserver.py
    
Será necessário se conectar utilizando o Google+ para ter acesso ao gerenciamento dos registros.