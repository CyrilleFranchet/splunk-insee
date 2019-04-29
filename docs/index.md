# Introduction
L’application Splunk INSEE a été développée afin de permettre la migration entre les fichiers XL2 de l’INSEE et la nouvelle API SIRENE (https://api.insee.fr/catalogue/).
Les anciens fichiers XL2 contenaient les mises à jour journalières fournies par l’INSEE. Aujourd’hui, l’API SIRENE permet seulement d’avoir une photo à un instant t.

# Fonctionnement de l'application
L’application INSEE fournit aux utilisateurs deux nouvelles « custom commands » aux utilsateurs de l’application Splunk.

## Commande insee
Commande génératrice d’événements qui interroge l’API SIRENE pour obtenir les établissements qui ont été modifiés à une date donnée.

La commande accepte différents paramètres optionnels :
- **dtr** : date à récupérer au format AAAA-MM-JJ. Le script récupère automatiquement les données de la veille si ce paramètre est omis ;
- **proxy** : booléen permettant d’activer l’usage des proxies mandataires définis dans le fichier de configuration ;
- **debug** : booléen permettant d’activer des journaux verbeux sur les données que traite la commande. Les journaux sont inscrits dans le fichier $SPLUNK_HOME/var/log/splunk/insee.log.

De plus, cette commande est configurée par un fichier de configuration JSON qui est placé dans le répertoire /bin/ de l’application Splunk. Son nom est configuration_json.txt. Voici son contenu :
```
{
    "consumer_key": "my_key",
    "consumer_secret": "my_secret",
    "http_proxy": "http://@127.0.0.1:3128",
    "https_proxy": "http://@127.0.0.1:3128",
    "endpoint_informations": "https://api.insee.fr/entreprises/sirene/V3/informations",
    "endpoint_etablissement": "https://api.insee.fr/entreprises/sirene/V3/siret",
    "endpoint_token": "https://api.insee.fr/token"
}
```
Les paramètres consumer correspondent aux identifiants de l’API SIRENE de l’INSEE et les deux URL aux proxies HTTP et HTTPS s’ils sont nécessaires à l’accès Internet.
Les URL de l'API permettent de modifier les URL des endpoints si l'INSEE les modifie.

## Commande xl2
Commande de rapport prenant des évènements Splunk en entrée pour les inscrire dans un fichier CSV dans un format où les colonnes sont séparées par des « ; » et où les valeurs sont entre «"».

La commande accepte un paramètre optionnel :
- **dtr** : date des données au format AAAA-MM-JJ. Le script utilise automatiquement la date de la veille si ce paramètre est omis. Cette date est utilisée pour horodater le fichier CSV en sortie. Les fichiers CSV sont enregistrés dans le répertoire $SPLUNK_HOME/var/run/splunk/csv/.

# Utilisation de lookups
Toutes les données ne sont pas extraites depuis l'API SIRENE. Certaines données sont récupérées à travers des fichiers CSV fournis par l'INSEE. L'appliation Splunk utilise trois lookups :
- **naf.csv** : contient les libellés des codes NAF correspondants ;
- **nj.csv** :  contient les libellés des statuts juridiques ;
- **pays.csv** : contient les codes des pays étrangers.

# Recherche type
La recherche suivante permet de récupérer les données de la veille et de les enregistrer dans un fichier CSV dont le nom est horodaté à la date de la veille.
```
| insee debug=true | extract limit=200 maxchars=100000 | lookup csv_naf ID as LIBAPET output LIBELLE as LIBAPET | lookup csv_naf ID as LIBAPEN output LIBELLE as LIBAPEN | lookup csv_nj ID as LIBNJ output LIBELLE as LIBNJ | lookup csv_pays CODE AS L7_NORMALISEE output PAYS as L7_NORMALISEE_2 | eval L7_NORMALISEE=coalesce(L7_NORMALISEE_2,L7_NORMALISEE) | fields - _time _raw event_no _kv | fields SIREN,NIC,L1_NORMALISEE,L2_NORMALISEE,L3_NORMALISEE,L4_NORMALISEE,L5_NORMALISEE,L6_NORMALISEE,L7_NORMALISEE,L1_DECLAREE,L2_DECLAREE,L3_DECLAREE,L4_DECLAREE,L5_DECLAREE,L6_DECLAREE,L7_DECLAREE,NUMVOIE,INDREP,TYPVOIE,LIBVOIE,CODPOS,CEDEX,RPET,LIBREG,DEPET,ARRONET,CTONET,COMET,LIBCOM,DU,TU,UU,EPCI,TCD,ZEMET,SIEGE,ENSEIGNE,IND_PUBLIPO,DIFFCOM,AMINTRET,NATETAB,LIBNATETAB,APET700,LIBAPET,DAPET,TEFET,LIBTEFET,EFETCENT,DEFET,ORIGINE,DCRET,DDEBACT,ACTIVNAT,LIEUACT,ACTISURF,SAISONAT,MODET,PRODET,PRODPART,AUXILT,NOMEN_LONG,SIGLE,NOM,PRENOM,CIVILITE,RNA,NICSIEGE,RPEN,DEPCOMEN,ADR_MAIL,NJ,LIBNJ,APEN700,LIBAPEN,DAPEN,APRM,ESS,DATEESS,TEFEN,LIBTEFEN,EFENCENT,DEFEN,CATEGORIE,DCREN,AMINTREN,MONOACT,MODEN,PRODEN,ESAANN,TCA,ESAAPEN,ESASEC1N,ESASEC2N,ESASEC3N,ESASEC4N,VMAJ,VMAJ1,VMAJ2,VMAJ3,DATEMAJ,EVE,DATEVE,TYPCREH,DREACTET,DREACTEN,MADRESSE,MENSEIGNE,MAPET,MPRODET,MAUXILT,MNOMEN,MSIGLE,MNICSIEGE,MNJ,MAPEN,MPRODEN,SIRETPS,TEL | xl2
```
A noter, l'utilisation des trois lookups précédemment détaillés dans le but d'insérer les bons libellés.

# Principe de fonctionnement de l'application
A chaque exécution, le script Python se connecte à l'API SIRENE pour obtenir la liste des SIRET qui ont été modifiés à la date demandée.
Le résultat est retourné par l'API en utilisant une notion de curseur car le volume de données est trop important pour être récupéré en une requête (voir documentation du service SIRENE).


Il est important de comprendre que l'API est mise à jour quotidiennement par l'INSEE donc il est nécessaire d'avoir une photo journalière pour maintenir un état cohérent par rapport à leur base.

Le script cherche ensuite dans cette liste de SIRET si ces établissements sont des sièges de l'unité légale. Dans la négative, le script se charge de récupérer les établissements sièges qui sont manquants, ceci lui permettant de récupérer l'adresse de l'établissement siège.
Le script implémente cette interrogation avec des query q (voir documentation du service SIRENE) à base de requêtes GET car elles étaient la seule solution à l'ouverture du service. Il existe depuis une version à base de requêtes POST (voir documentation du service SIRENE).
Cette interrogation à base de GET est limité en taille et donc le script est obligé de multiplier les requêtes pour récupérer une liste importante d'établissements siège. Il est important de rappeler que le nombre de requêtes par minute est limité à 30.

Le script traite ensuite les données pour produire les évènements Splunk qui sont attendus.

# Resynchronisation de l'application sur la version GitHub
Il suffit pour cela de se positionner dans le répertoire de l'application Splunk et de synchroniser le repository.

```
cd $SPLUNK_HOME/etc/apps/splunk-insee
git pull
```

Il est préférable de redémarrer Splunk.

# Gestion des messages d'erreur
Par défaut, la commande interroge le endpoint informations afin de récupérer des informations telles que :
- Une information sur la version actuelle de l'API ;
- des informations sur les dates de mises à jour des différentes données exposées par l'API Sirene ;
  - collection : nom de la collection
  - dateDerniereMiseADisposition : date et heure de la dernière mise à disposition des données de la collection ;
  - dateDernierTraitementMaximum : date correspondant à la date de validité des données consultées ;
  - dateDernierTraitementDeMasse : date du dernier traitement de masse sur la collection. À cette date plusieurs centaines de milliers de documents ont pu être mis à jour. Il est conseillé de traiter cette date d'une manière spécifique.

Ceci permet d'avoir des informations sur la dernière date de publication concernant les établissements, la date de dernier traitement de masse, etc.

De plus, si la commande fonctionne correctement, elle inscrit les informations suivantes dans le fichier de journalisation insee.log :
- Le nombre d'établissements modifiés à la date demandée ;
- le nombre d'établissements siège réellement récupérés par rapport au nombre à récupérer ;
- les éventuels établissements dont le siège pose un problème ;
- le nombre d'évènements finalement générés dans Splunk. Ce nombre doit être égal au nombre d'établissements modifiés à la date demandée.

```
2019-04-18 06:01:08,770, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=622,   found 4919 SIRET to delete
2019-04-18 06:01:08,770, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=621,   found 12816 SIRET to create
2019-04-18 06:01:08,770, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=620,   generated 17735 events
2019-04-18 06:01:04,367, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=531,   siret 38375385200029 has an invalid headquarter 38375385200037
2019-04-18 06:01:03,999, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=268,   retrieved 2948 of 2949 headquarters
2019-04-18 06:00:13,999, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=373,   retrieved 17735 siret to update
2019-04-18 06:00:01,918, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=362,   collection Liens de succession dateDerniereMiseADisposition 2019-04-17T10:57:07 dateDernierTraitementMaximum 2019-04-16T19:35:21 
2019-04-18 06:00:01,918, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=362,   collection Établissements dateDerniereMiseADisposition 2019-04-17T23:56:14 dateDernierTraitementDeMasse 2018-09-30 dateDernierTraitementMaximum 2019-04-17T20:45:41 
2019-04-18 06:00:01,918, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=362,   collection Unités Légales dateDerniereMiseADisposition 2019-04-17T23:33:15 dateDernierTraitementDeMasse 2018-09-30 dateDernierTraitementMaximum 2019-04-17T20:45:41 
2019-04-18 06:00:01,918, Level=INFO, Pid=3121, Logger=INSEECommand, File=insee.py, Line=343,   versionService 3.6.3
```

Il apparaît à l'usage que l'INSEE ne met pas toujours les données à disposition en temps et en heure. Dans ce cas, le script ne fonctionne pas car les données sont inexistantes.
L'exemple ci-dessous montre ce type d'erreur dans les journaux.

```
2019-04-25 06:00:03,255, Level=ERROR, Pid=18233, Logger=INSEECommand, File=insee.py, Line=175,   unknown siret: Aucun élément trouvé pour q=dateDernierTraitementEtablissement:2019-04-24
2019-04-25 06:00:02,874, Level=INFO, Pid=18233, Logger=INSEECommand, File=insee.py, Line=362,   collection Liens de succession dateDerniereMiseADisposition 2019-04-23T23:37:03 dateDernierTraitementMaximum 2019-04-23T21:06:08 
2019-04-25 06:00:02,874, Level=INFO, Pid=18233, Logger=INSEECommand, File=insee.py, Line=362,   collection Établissements dateDerniereMiseADisposition 2019-04-23T23:36:42 dateDernierTraitementDeMasse 2018-09-30 dateDernierTraitementMaximum 2019-04-23T21:28:48 
2019-04-25 06:00:02,873, Level=INFO, Pid=18233, Logger=INSEECommand, File=insee.py, Line=362,   collection Unités Légales dateDerniereMiseADisposition 2019-04-23T23:12:57 dateDernierTraitementDeMasse 2018-09-30 dateDernierTraitementMaximum 2019-04-23T21:28:48 
2019-04-25 06:00:02,872, Level=INFO, Pid=18233, Logger=INSEECommand, File=insee.py, Line=343,   versionService 3.6.3
```

Ici, l'information importante est :
```
Aucun élément trouvé pour q=dateDernierTraitementEtablissement:2019-04-24
```

Ceci se confirme par le fait que la date dateDerniereMiseADisposition est positionnée au 2019-04-23T23:36:42.
Dans tel cas, il est nécessaire de relancer la commande manuellement en suivant le paragraphe suivant. Il peut aussi être judicieux de modifier l'heure d'exécution de la recherche sur Splunk.

# Récupération d'une journée en cas d'erreur
Toutes les journées doivent être récupérées manuellement en spécifiant la date manquante car les données sont cumulatives.

Exemple, ici nous récupérons manuellement la date du 13 avril 2019 :

```
| insee dtr=2019-04-13 debug=true | extract limit=200 maxchars=100000 | lookup csv_naf ID as LIBAPET output LIBELLE as LIBAPET | lookup csv_naf ID as LIBAPEN output LIBELLE as LIBAPEN | lookup csv_nj ID as LIBNJ output LIBELLE as LIBNJ | lookup csv_pays CODE AS L7_NORMALISEE output PAYS as L7_NORMALISEE_2 | eval L7_NORMALISEE=coalesce(L7_NORMALISEE_2,L7_NORMALISEE) | fields - _time _raw event_no _kv | fields SIREN,NIC,L1_NORMALISEE,L2_NORMALISEE,L3_NORMALISEE,L4_NORMALISEE,L5_NORMALISEE,L6_NORMALISEE,L7_NORMALISEE,L1_DECLAREE,L2_DECLAREE,L3_DECLAREE,L4_DECLAREE,L5_DECLAREE,L6_DECLAREE,L7_DECLAREE,NUMVOIE,INDREP,TYPVOIE,LIBVOIE,CODPOS,CEDEX,RPET,LIBREG,DEPET,ARRONET,CTONET,COMET,LIBCOM,DU,TU,UU,EPCI,TCD,ZEMET,SIEGE,ENSEIGNE,IND_PUBLIPO,DIFFCOM,AMINTRET,NATETAB,LIBNATETAB,APET700,LIBAPET,DAPET,TEFET,LIBTEFET,EFETCENT,DEFET,ORIGINE,DCRET,DDEBACT,ACTIVNAT,LIEUACT,ACTISURF,SAISONAT,MODET,PRODET,PRODPART,AUXILT,NOMEN_LONG,SIGLE,NOM,PRENOM,CIVILITE,RNA,NICSIEGE,RPEN,DEPCOMEN,ADR_MAIL,NJ,LIBNJ,APEN700,LIBAPEN,DAPEN,APRM,ESS,DATEESS,TEFEN,LIBTEFEN,EFENCENT,DEFEN,CATEGORIE,DCREN,AMINTREN,MONOACT,MODEN,PRODEN,ESAANN,TCA,ESAAPEN,ESASEC1N,ESASEC2N,ESASEC3N,ESASEC4N,VMAJ,VMAJ1,VMAJ2,VMAJ3,DATEMAJ,EVE,DATEVE,TYPCREH,DREACTET,DREACTEN,MADRESSE,MENSEIGNE,MAPET,MPRODET,MAUXILT,MNOMEN,MSIGLE,MNICSIEGE,MNJ,MAPEN,MPRODEN,SIRETPS,TEL | xl2 dtr=2019-04-13
```