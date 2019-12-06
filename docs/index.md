# Introduction
L’application Splunk INSEE a été développée afin de permettre la migration entre les fichiers XL2 de l’INSEE et la nouvelle API SIRENE (https://api.insee.fr/catalogue/).
Les anciens fichiers XL2 contenaient les mises à jour journalières fournies par l’INSEE. Aujourd’hui, l’API SIRENE permet seulement d’avoir une photo à un instant t.

# Fonctionnement de l'application
L’application INSEE fournit deux nouvelles « custom commands » aux utilisateurs de l’application Splunk.

## Commande insee
Commande génératrice d’événements qui interroge l’API SIRENE pour obtenir les établissements qui ont été modifiés à une date donnée.

La commande accepte différents paramètres optionnels :
- **dtr** : date à récupérer au format AAAA-MM-JJ. Le script récupère automatiquement les données de la veille si ce paramètre est omis ;
- **proxy** : booléen permettant d’activer l’usage des proxies mandataires définis dans le fichier de configuration ;
- **debug** : booléen permettant d’activer des journaux verbeux sur les données que traite la commande. Les journaux sont inscrits dans le fichier $SPLUNK_HOME/var/log/splunk/insee.log.

Des constraintes sont effectuées sur ces options, de sorte à vérifier que le format de données est correct.

Les valeurs acceptées pour les booléens sont :
- valeurs vraies : 1, t, true, y, yes
- valeurs fausses : 0, f, false, n, no

De plus, cette commande est configurée par un fichier de configuration JSON qui est placé dans le répertoire /bin/ de l’application Splunk.

Son nom est configuration_json.txt et voici son contenu :
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

NB : la fonction map() de la commande xl2 est appelée à chaque chunck de données (50.000 événements par défaut) et elle inscrit les données dans un CSV temporaire en mode append.0
La fonction reduce() de la commande xl2 est appelée une fois à la fin de la récupération afin d'écrire un fichier final avec l'entête et les données précédemment récupérées et sous forme de ZIP.

La commande accepte un paramètre optionnel :
- **dtr** : date des données au format AAAA-MM-JJ. Le script utilise automatiquement la date de la veille si ce paramètre est omis. Cette date est utilisée pour horodater le fichier CSV en sortie. Les fichiers CSV sont enregistrés dans le répertoire $SPLUNK_HOME/var/run/splunk/csv/.

# Utilisation de lookups
Toutes les données ne sont pas extraites depuis l'API SIRENE. Certaines données sont récupérées à travers des fichiers CSV fournis par l'INSEE. L'application Splunk utilise trois lookups :
- **naf.csv** : contient les libellés des codes NAF correspondants ;
- **nj.csv** :  contient les libellés des statuts juridiques ;
- **pays.csv** : contient les codes des pays étrangers.

Il est nécessaire de mettre à jour ces fichiers dans Splunk si l'INSEE vient à les mettre à jour.

ATTENTION : Splunk utilise le format Comma Separated Value et il peut être nécessaire de remplacer les ";" par des ",". 

Splunk nécessite que la première ligne de ces fichiers soit positionnée à la valeur suivante :
- naf.csv : ID,LIBELLE
- nj.csv : ID,LIBELLE
- pays.csv : CODE,PAYS

# Recherche type
La recherche suivante permet de récupérer les données de la veille et de les enregistrer dans un fichier CSV dont le nom est horodaté à la date de la veille.
```
| insee proxy=true | extract limit=200 maxchars=100000 | lookup csv_naf ID as LIBAPET output LIBELLE as LIBAPET | lookup csv_naf ID as LIBAPEN output LIBELLE as LIBAPEN | lookup csv_nj ID as LIBNJ output LIBELLE as LIBNJ | lookup csv_pays CODE AS L7_NORMALISEE output PAYS as L7_NORMALISEE_2 | eval L7_NORMALISEE=coalesce(L7_NORMALISEE_2,L7_NORMALISEE) | fields SIREN,NIC,L1_NORMALISEE,L2_NORMALISEE,L3_NORMALISEE,L4_NORMALISEE,L5_NORMALISEE,L6_NORMALISEE,L7_NORMALISEE,L1_DECLAREE,L2_DECLAREE,L3_DECLAREE,L4_DECLAREE,L5_DECLAREE,L6_DECLAREE,L7_DECLAREE,NUMVOIE,INDREP,TYPVOIE,LIBVOIE,CODPOS,CEDEX,RPET,LIBREG,DEPET,ARRONET,CTONET,COMET,LIBCOM,DU,TU,UU,EPCI,TCD,ZEMET,SIEGE,ENSEIGNE,IND_PUBLIPO,DIFFCOM,AMINTRET,NATETAB,LIBNATETAB,APET700,LIBAPET,DAPET,TEFET,LIBTEFET,EFETCENT,DEFET,ORIGINE,DCRET,DDEBACT,ACTIVNAT,LIEUACT,ACTISURF,SAISONAT,MODET,PRODET,PRODPART,AUXILT,NOMEN_LONG,SIGLE,NOM,PRENOM,CIVILITE,RNA,NICSIEGE,RPEN,DEPCOMEN,ADR_MAIL,NJ,LIBNJ,APEN700,LIBAPEN,DAPEN,APRM,ESS,DATEESS,TEFEN,LIBTEFEN,EFENCENT,DEFEN,CATEGORIE,DCREN,AMINTREN,MONOACT,MODEN,PRODEN,ESAANN,TCA,ESAAPEN,ESASEC1N,ESASEC2N,ESASEC3N,ESASEC4N,VMAJ,VMAJ1,VMAJ2,VMAJ3,DATEMAJ,EVE,DATEVE,TYPCREH,DREACTET,DREACTEN,MADRESSE,MENSEIGNE,MAPET,MPRODET,MAUXILT,MNOMEN,MSIGLE,MNICSIEGE,MNJ,MAPEN,MPRODEN,SIRETPS,TEL | xl2
```

## Détails de la commande

```| insee proxy=true```

La commande insee récupère les données de la veille en interrogeant l'API SIRENE.

```| extract limit=200 maxchars=100000```

Il est indiqué à Splunk d'extraire les key=value automatiquement en lui indiquant que nous avons au moins 200 champs sur une ligne avec un au maximum 100000 caractères sur cette ligne.

```| lookup csv_naf ID as LIBAPET output LIBELLE as LIBAPET```

Splunk ouvre le fichier csv_naf.csv et cherche la valeur LIBAPET dans la colonne ID afin de remplacer LIBAPET par la valeur de la colonne LIBELLE.

```| lookup csv_naf ID as LIBAPEN output LIBELLE as LIBAPEN```

Splunk ouvre le fichier csv_naf.csv et cherche la valeur LIBAPEN dans la colonne ID afin de remplacer LIBAPEN par la valeur de la colonne LIBELLE.

```| lookup csv_nj ID as LIBNJ output LIBELLE as LIBNJ```

Splunk ouvre le fichier csv_nj.csv et cherche la valeur LIBNJ dans la colonne ID afin de remplacer LIBNJ par la valeur de la colonne LIBELLE.

```| lookup csv_pays CODE AS L7_NORMALISEE output PAYS as L7_NORMALISEE_2```

Splunk ouvre le fichier csv_pays.csv et cherche la valeur L7_NORMALISEE dans la colonne CODE afin de positionner L7_NORMALISEE_2 à la valeur de la colonne PAYS.

```| eval L7_NORMALISEE=coalesce(L7_NORMALISEE_2,L7_NORMALISEE)```

Splunk positionne la valeur de L7_NORMALISEE à la valeur de L7_NORMALISEE_2 si ce champ n'est pas nul. Si ce n'est pas le cas, Splunk utilise la valeur de L7_NORMALISEE.

```| fields SIREN,NIC,L1_NORMALISEE,L2_NORMALISEE,L3_NORMALISEE,L4_NORMALISEE,L5_NORMALISEE,L6_NORMALISEE,L7_NORMALISEE,L1_DECLAREE,L2_DECLAREE,L3_DECLAREE,L4_DECLAREE,L5_DECLAREE,L6_DECLAREE,L7_DECLAREE,NUMVOIE,INDREP,TYPVOIE,LIBVOIE,CODPOS,CEDEX,RPET,LIBREG,DEPET,ARRONET,CTONET,COMET,LIBCOM,DU,TU,UU,EPCI,TCD,ZEMET,SIEGE,ENSEIGNE,IND_PUBLIPO,DIFFCOM,AMINTRET,NATETAB,LIBNATETAB,APET700,LIBAPET,DAPET,TEFET,LIBTEFET,EFETCENT,DEFET,ORIGINE,DCRET,DDEBACT,ACTIVNAT,LIEUACT,ACTISURF,SAISONAT,MODET,PRODET,PRODPART,AUXILT,NOMEN_LONG,SIGLE,NOM,PRENOM,CIVILITE,RNA,NICSIEGE,RPEN,DEPCOMEN,ADR_MAIL,NJ,LIBNJ,APEN700,LIBAPEN,DAPEN,APRM,ESS,DATEESS,TEFEN,LIBTEFEN,EFENCENT,DEFEN,CATEGORIE,DCREN,AMINTREN,MONOACT,MODEN,PRODEN,ESAANN,TCA,ESAAPEN,ESASEC1N,ESASEC2N,ESASEC3N,ESASEC4N,VMAJ,VMAJ1,VMAJ2,VMAJ3,DATEMAJ,EVE,DATEVE,TYPCREH,DREACTET,DREACTEN,MADRESSE,MENSEIGNE,MAPET,MPRODET,MAUXILT,MNOMEN,MSIGLE,MNICSIEGE,MNJ,MAPEN,MPRODEN,SIRETPS,TEL```

Les champs suivants sont fournis à la commande xl2.

```| xl2```

La commande xl2 est appelée afin d'écrire les résultats dans le fichier CSV final en séparant les champs par un ";" et en entourant les valeurs avec le caractère ".


# Principe de fonctionnement de l'application
A chaque exécution, le script Python se connecte à l'API SIRENE pour obtenir la liste des SIRET qui ont été modifiés à la date demandée.
Le résultat est retourné par l'API en utilisant une notion de curseur car le volume de données est trop important pour être récupéré en une requête (voir documentation du service SIRENE).


Il est important de comprendre que l'API est mise à jour quotidiennement par l'INSEE donc il est nécessaire d'avoir une photo journalière pour maintenir un état cohérent par rapport à leur base.

Le script cherche ensuite dans cette liste de SIRET si ces établissements sont des sièges de l'unité légale. Dans la négative, le script se charge de récupérer les établissements sièges qui sont manquants, ceci lui permettant de récupérer l'adresse de l'établissement siège.
Le script implémente cette interrogation avec des query q (voir documentation du service SIRENE) à base de requêtes GET car elles étaient la seule solution à l'ouverture du service. Il existe depuis une version à base de requêtes POST (voir documentation du service SIRENE).
Cette interrogation à base de GET est limitée en taille et donc le script est obligé de multiplier les requêtes pour récupérer une liste importante d'établissements siège. Il est important de rappeler que le nombre de requêtes par minute est limité à 30.

Le script traite ensuite les données pour produire les évènements Splunk qui sont attendus.

# Resynchronisation de l'application sur la version GitHub
Il suffit pour cela de se positionner dans le répertoire de l'application Splunk et de synchroniser le repository.

```
cd $SPLUNK_HOME/etc/apps/splunk-insee
git pull
```

Normalement, Splunk n'a pas besoin d'être redémarré lorsque le code Python est modifié.

# Gestion des messages d'erreur
Par défaut, la commande interroge le endpoint informations afin de récupérer des informations telles que :
- Une information sur la version actuelle de l'API ;
- des informations sur les dates de mises à jour des différentes données exposées par l'API Sirene :
  - collection : nom de la collection
  - dateDerniereMiseADisposition : date et heure de la dernière mise à disposition des données de la collection ;
  - dateDernierTraitementMaximum : date correspondant à la date de validité des données consultées ;
  - dateDernierTraitementDeMasse : date du dernier traitement de masse sur la collection. À cette date plusieurs centaines de milliers de documents ont pu être mis à jour. Il est conseillé de traiter cette date d'une manière spécifique.

De plus, si la commande fonctionne correctement, elle inscrit les informations suivantes dans le fichier de journalisation insee.log :
- Le nombre d'établissements modifiés à la date demandée ;
- le nombre d'établissements siège réellement récupérés par rapport au nombre à récupérer ;
- les éventuels établissements dont le siège pose un problème ;
- le nombre d'évènements finalement générés dans Splunk. Ce nombre doit être égal au nombre d'établissements modifiés à la date demandée.

NB : les siret sont récupérés par bloc de 1000 afin de pouvoir traiter un volume conséquent de données.
Il est toutefois important de souligner que Splunk attend que la commande insee.py se termine avant de continuer le pipeline d'exécution.
Il faut juste éviter que Python manipule des millions d'objet en mémoire vive.

```
2019-12-04 12:21:38,370, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=621,   versionService 3.8.3
2019-12-04 12:21:38,371, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=640,   collection Unités Légales dateDerniereMiseADisposition 2019-12-03T23:44:34 dateDernierTraitementDeMasse 2019-06-24 dateDernierTraitementMaximum 2019-12-03T22:31:35
2019-12-04 12:21:38,371, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=640,   collection Établissements dateDerniereMiseADisposition 2019-12-04T00:28:03 dateDernierTraitementDeMasse 2019-06-24 dateDernierTraitementMaximum 2019-12-03T22:31:35
2019-12-04 12:21:38,371, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=640,   collection Liens de succession dateDerniereMiseADisposition 2019-12-04T00:28:29 dateDernierTraitementMaximum 2019-12-03T20:38:54
2019-12-04 12:21:39,959, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=657,   retrieved a total of 20806 siret to update
2019-12-04 12:21:39,960, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:21:39,960, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 1000 siret / 20806
2019-12-04 12:21:42,027, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 311 of 311 headquarters
2019-12-04 12:21:43,909, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:21:43,910, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 2000 siret / 20806
2019-12-04 12:21:48,817, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 323 of 323 headquarters
2019-12-04 12:21:50,617, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:21:50,617, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 3000 siret / 20806
2019-12-04 12:21:52,226, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 337 of 337 headquarters
2019-12-04 12:21:54,344, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:21:54,345, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 4000 siret / 20806
2019-12-04 12:21:55,902, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 268 of 268 headquarters
2019-12-04 12:21:57,704, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:21:57,704, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 5000 siret / 20806
2019-12-04 12:21:58,124, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 73 of 73 headquarters
2019-12-04 12:21:59,755, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:21:59,755, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 6000 siret / 20806
2019-12-04 12:22:00,102, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 8 of 8 headquarters
2019-12-04 12:22:01,784, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:01,784, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 7000 siret / 20806
2019-12-04 12:22:02,137, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 6 of 6 headquarters
2019-12-04 12:22:03,746, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:03,746, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 8000 siret / 20806
2019-12-04 12:22:04,090, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 5 of 5 headquarters
2019-12-04 12:22:05,846, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:05,846, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 9000 siret / 20806
2019-12-04 12:22:06,199, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 5 of 5 headquarters
2019-12-04 12:22:07,827, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:07,827, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 10000 siret / 20806
2019-12-04 12:22:08,180, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 7 of 7 headquarters
2019-12-04 12:22:09,838, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:09,838, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 11000 siret / 20806
2019-12-04 12:22:10,209, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 3 of 3 headquarters
2019-12-04 12:22:11,852, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:11,852, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 12000 siret / 20806
2019-12-04 12:22:12,245, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 8 of 8 headquarters
2019-12-04 12:22:14,503, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:14,503, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 13000 siret / 20806
2019-12-04 12:22:14,895, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 1 of 1 headquarters
2019-12-04 12:22:16,654, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:16,655, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 14000 siret / 20806
2019-12-04 12:22:17,018, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 1 of 1 headquarters
2019-12-04 12:22:18,602, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:18,603, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 15000 siret / 20806
2019-12-04 12:22:18,964, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 3 of 3 headquarters
2019-12-04 12:22:20,590, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:20,590, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 16000 siret / 20806
2019-12-04 12:22:20,933, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 1 of 1 headquarters
2019-12-04 12:22:22,929, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:22,929, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 17000 siret / 20806
2019-12-04 12:22:23,287, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 1 of 1 headquarters
2019-12-04 12:22:24,860, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:24,860, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 18000 siret / 20806
2019-12-04 12:22:25,226, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 5 of 5 headquarters
2019-12-04 12:22:26,963, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:26,963, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 19000 siret / 20806
2019-12-04 12:22:27,307, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 2 of 2 headquarters
2019-12-04 12:22:29,073, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 1000 siret to update in this window
2019-12-04 12:22:29,073, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 20000 siret / 20806
2019-12-04 12:22:29,433, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 10 of 10 headquarters
2019-12-04 12:22:30,824, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 806 siret to update in this window
2019-12-04 12:22:30,824, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 20806 siret / 20806
2019-12-04 12:22:31,187, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 5 of 5 headquarters
2019-12-04 12:22:31,794, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=659,   retrieved 0 siret to update in this window
2019-12-04 12:22:31,795, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=661,   retrieved 20806 siret / 20806
2019-12-04 12:22:31,795, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=361,   retrieved 0 of 0 headquarters
2019-12-04 12:22:31,795, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=682,   generated 20806 events
2019-12-04 12:22:31,795, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=683,   found 19853 SIRET to create
2019-12-04 12:22:31,795, Level=INFO, Pid=32337, Logger=INSEECommand, File=insee.py, Line=684,   found 953 SIRET to delete
```

Il apparaît à l'usage que l'INSEE ne met pas toujours les données à disposition en temps et en heure. Dans ce cas, le script ne fonctionne pas car les données sont inexistantes.
L'exemple ci-dessous montre ce type d'erreur dans les journaux.

```
2019-12-04 12:22:57,326, Level=INFO, Pid=32489, Logger=INSEECommand, File=insee.py, Line=621,   versionService 3.8.3
2019-12-04 12:22:57,327, Level=INFO, Pid=32489, Logger=INSEECommand, File=insee.py, Line=640,   collection Unités Légales dateDerniereMiseADisposition 2019-12-03T23:44:34 dateDernierTraitementDeMasse 2019-06-24 dateDernierTraitementMaximum 2019-12-03T22:31:35
2019-12-04 12:22:57,327, Level=INFO, Pid=32489, Logger=INSEECommand, File=insee.py, Line=640,   collection Établissements dateDerniereMiseADisposition 2019-12-04T00:28:03 dateDernierTraitementDeMasse 2019-06-24 dateDernierTraitementMaximum 2019-12-03T22:31:35
2019-12-04 12:22:57,328, Level=INFO, Pid=32489, Logger=INSEECommand, File=insee.py, Line=640,   collection Liens de succession dateDerniereMiseADisposition 2019-12-04T00:28:29 dateDernierTraitementMaximum 2019-12-03T20:38:54
2019-12-04 12:22:57,678, Level=ERROR, Pid=32489, Logger=INSEECommand, File=insee.py, Line=291,   unknown siret: Aucun élément trouvé pour q=dateDernierTraitementEtablissement:2019-12-04
```

Ici, l'information importante est :
```
Aucun élément trouvé pour q=dateDernierTraitementEtablissement:2019-12-04
```

Ceci se confirme par le fait que la date dateDerniereMiseADisposition est positionnée au 2019-12-04T00:28:03.
Dans tel cas, il est nécessaire de relancer la commande manuellement en suivant le paragraphe suivant. Il peut aussi être judicieux de modifier l'heure d'exécution de la recherche sur Splunk.

La commande INSEE journalise des messages avec trois niveaux de criticité :
- INFO : le message est purement informatif ;
- ERROR : le message est critique car la commande ne s'est pas exécutée correctement. Il sera nécessaire de la relancer manuellement après diagnostique ;
- DEBUG : le message est utile au développeur Python et la commande a été lançée avec l'option debug activée.

Pour finir, il est préférable de mettre en place des recherches planifiées afin de vérifier le fichier insee.log à chaque exécution de la commande insee pour vérifier que cette dernière s'est exécutée correctement.

# Gestion des Exception Python
Des exceptions Python ont été créées afin qu'elles soient levées pour indiquer à Splunk que la commande a rencontré une erreur.
Ce sont ces erreurs qui sont affichées dans la GUI en cas d'erreur rencontrée par la commande insee.

Voici la liste de ces exceptions :
- ExceptionTranslation : problème rencontré lors du mapping entre XL2 et les champs de l'API ;
- ExceptionHeadquarters : problème rencontré lors de la récupération des établissements siège ;
- ExceptionUpdatedSiret : problème rencontré lors de la récupération des SIRET mis à jour par l'INSEE ;
- ExceptionSiret : problème rencontré lors de l'interrogation du endpoint siret de l'API SIRENE ;
- ExceptionStatus : problème rencontré lors de l'interrogation du endpoint information de l'API SIRENE ;
- ExceptionToken : problème rencontré lors de l'interrogation du endpoint token de l'API SIRENE ;
- ExceptionConfiguration : problème rencontré lors du chargement du fichier de configuration JSON.

A noter, que le code Python des commandes insee.py et xl2.py attrape toutes les exceptions Python qui ne sont pas gérées.

Dans tel cas, ce genre de message est inscrit dans le fichier de journalisation insee.log :
```
2019-05-14 14:02:08,789, Level=ERROR, Pid=18096, Logger=INSEECommand, File=insee.py, Line=662,   unhandled exception has occurred. Traceback is in splunklib.log: HTTPSConnectionPool(host='api.insee.fr', port=443): Max retries exceeded with url: /token (Caused by <class 'socket.error'>: [Errno 110] Connection timed out)
```

Le message indique que la backtrace Python est dans le fichier splunklib.log. Il est important de noter que ce genre de message nécessite une attention particulière, car ceci signifie que le code a rencontré une situation non habituelle et qu'il ne sait pas gérer correctement.

Dans ce cas, l'exception non gérée est aussi reçue par la GUI Splunk.

# Récupération d'une journée en cas d'erreur
Toutes les journées doivent être récupérées manuellement en spécifiant la date manquante car les données sont cumulatives.

Exemple, ici nous récupérons manuellement la date du 13 avril 2019 :

```
| insee dtr=2019-04-13 proxy=true | extract limit=200 maxchars=100000 | lookup csv_naf ID as LIBAPET output LIBELLE as LIBAPET | lookup csv_naf ID as LIBAPEN output LIBELLE as LIBAPEN | lookup csv_nj ID as LIBNJ output LIBELLE as LIBNJ | lookup csv_pays CODE AS L7_NORMALISEE output PAYS as L7_NORMALISEE_2 | eval L7_NORMALISEE=coalesce(L7_NORMALISEE_2,L7_NORMALISEE) | fields SIREN,NIC,L1_NORMALISEE,L2_NORMALISEE,L3_NORMALISEE,L4_NORMALISEE,L5_NORMALISEE,L6_NORMALISEE,L7_NORMALISEE,L1_DECLAREE,L2_DECLAREE,L3_DECLAREE,L4_DECLAREE,L5_DECLAREE,L6_DECLAREE,L7_DECLAREE,NUMVOIE,INDREP,TYPVOIE,LIBVOIE,CODPOS,CEDEX,RPET,LIBREG,DEPET,ARRONET,CTONET,COMET,LIBCOM,DU,TU,UU,EPCI,TCD,ZEMET,SIEGE,ENSEIGNE,IND_PUBLIPO,DIFFCOM,AMINTRET,NATETAB,LIBNATETAB,APET700,LIBAPET,DAPET,TEFET,LIBTEFET,EFETCENT,DEFET,ORIGINE,DCRET,DDEBACT,ACTIVNAT,LIEUACT,ACTISURF,SAISONAT,MODET,PRODET,PRODPART,AUXILT,NOMEN_LONG,SIGLE,NOM,PRENOM,CIVILITE,RNA,NICSIEGE,RPEN,DEPCOMEN,ADR_MAIL,NJ,LIBNJ,APEN700,LIBAPEN,DAPEN,APRM,ESS,DATEESS,TEFEN,LIBTEFEN,EFENCENT,DEFEN,CATEGORIE,DCREN,AMINTREN,MONOACT,MODEN,PRODEN,ESAANN,TCA,ESAAPEN,ESASEC1N,ESASEC2N,ESASEC3N,ESASEC4N,VMAJ,VMAJ1,VMAJ2,VMAJ3,DATEMAJ,EVE,DATEVE,TYPCREH,DREACTET,DREACTEN,MADRESSE,MENSEIGNE,MAPET,MPRODET,MAUXILT,MNOMEN,MSIGLE,MNICSIEGE,MNJ,MAPEN,MPRODEN,SIRETPS,TEL | xl2 dtr=2019-04-13
```

A noter, qu'il n'est pas nécessaire de configurer le time range de Splunk. La commande est pleinement autonome.