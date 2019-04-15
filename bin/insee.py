#!/usr/bin/env python
# coding: utf-8

import sys
import time
import requests
from datetime import date, timedelta, datetime
from requests.auth import HTTPBasicAuth
from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
from splunklib import six
from collections import OrderedDict
import json
import os


class Date(validators.Validator):
    """
        Validates Date option values.
    """
    def __call__(self, value):
        if value is None:
            return None

        try:
            datetime.strptime(value, '%Y-%m-%d')
            return value
        except ValueError:
            raise ValueError('Unrecognized date value: {0}. Should be AAAA-MM-JJ'.format(value))

    def format(self, value):
        if value is None:
            return None
        return six.text_type(value)


@Configuration(type='events')
class INSEECommand(GeneratingCommand):
    """ Synopsis

    ##Syntax

    | insee [dtr=date_to_retrieve] [proxy=true] [debug=true]

    ##Description

    Request the Sirene API

    """
    dtr = Option(require=False, validate=Date())
    debug = Option(require=False, validate=validators.Boolean())
    proxy = Option(require=False, validate=validators.Boolean())

    def set_configuration(self):
        # Open the configuration file
        try:
            with open(os.path.dirname(os.path.abspath(__file__)) + '/configuration_json.txt', 'r') as conf_file:
                conf = json.load(conf_file)
        except ValueError:
            self.logger.error('  invalid JSON configuration file')
            exit(1)
        except IOError:
            self.logger.error('  configuration file doesn\'t exist')
            exit(1)

        # Verify the configuration
        if self.proxy:
            if 'http_proxy' not in conf or 'https_proxy' not in conf:
                self.logger.error('  proxies are not defined in the configuration file')
                exit(1)
            self.proxies = dict()
            self.proxies['http'] = conf['http_proxy']
            self.proxies['https'] = conf['https_proxy']

        if 'consumer_key' not in conf or 'consumer_secret' not in conf:
            self.logger.error('  API credentials are not defined in the configuration file')
            exit(1)

        if 'endpoint_token' not in conf or 'endpoint_etablissement' not in conf or 'endpoint_informations' not in conf:
            self.logger.error('  API endpoints are not defined in the configuration file')
            exit(1)

        self.consumer_key = conf['consumer_key']
        self.consumer_secret = conf['consumer_secret']
        self.endpoint_token = conf['endpoint_token']
        self.endpoint_etablissement = conf['endpoint_etablissement']
        self.endpoint_informations = conf['endpoint_informations']
        self.bearer_token = self.get_api_token()

    def get_api_token(self):
        payload = {'grant_type': 'client_credentials'}
        basic_auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        if self.proxy:
            r = requests.post(self.endpoint_token, auth=basic_auth, data=payload, proxies=self.proxies)
        else:
            r = requests.post(self.endpoint_token, auth=basic_auth, data=payload)
        if r.status_code == 200:
            return r.json()['access_token']
        elif r.status_code == 401:
            self.logger.error('  incorrect credentials : %s', r.json()['error_description'])
        else:
            self.logger.error('  error during token retrieval. Code received : %d', r.status_code)
        exit(1)

    def get_status(self):
        # Initialize
        headers = {'Authorization': 'Bearer ' + self.bearer_token}

        if self.proxy:
            r = requests.get(self.endpoint_informations, headers=headers,
                             proxies=self.proxies)
        else:
            r = requests.get(self.endpoint_informations, headers=headers)

        while r.status_code == 429:
            # We made too many requests. We wait for the next rounded minute
            current_second = datetime.now().time().strftime('%S')
            time.sleep(60 - int(current_second) + 1)
            if self.proxy:
                r = requests.get(self.endpoint_informations, headers=headers,
                                 proxies=self.proxies)
            else:
                r = requests.get(self.endpoint_informations, headers=headers)

        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            self.logger.error('  invalid bearer token %s in status request', self.bearer_token)
        elif r.status_code == 406:
            self.logger.error('  invalid Accept header in status request')
        else:
            self.logger.error('  error during status retrieval. Code received : %d', r.status_code)
        return None

    def get_siret(self, q=None, nombre=None, curseur=None, champs=None, gzip=False):
        # Initialize
        payload = dict()
        if champs:
            payload['champs'] = champs
        if q:
            payload['q'] = q
        if nombre:
            payload['nombre'] = nombre
        if curseur:
            payload['curseur'] = curseur

        headers = {'Authorization': 'Bearer ' + self.bearer_token}

        if gzip:
            # Request GZip content
            headers['Accept-Encoding'] = 'gzip'

        if self.proxy:
            r = requests.get(self.endpoint_etablissement, headers=headers, params=payload,
                             proxies=self.proxies)
        else:
            r = requests.get(self.endpoint_etablissement, headers=headers, params=payload)

        while r.status_code == 429:
            # We made too many requests. We wait for the next rounded minute
            current_second = datetime.now().time().strftime('%S')
            time.sleep(60 - int(current_second) + 1)
            if self.proxy:
                r = requests.get(self.endpoint_etablissement, headers=headers, params=payload,
                                 proxies=self.proxies)
            else:
                r = requests.get(self.endpoint_etablissement, headers=headers, params=payload)

        if r.status_code == 200:
            return r.json()
        elif r.status_code == 400:
            self.logger.error('  invalid parameters in query: %s', r.json()['header']['message'])
        elif r.status_code == 401:
            self.logger.error('  invalid bearer token %s in siret request', self.bearer_token)
        elif r.status_code == 404:
            self.logger.error('  unknown siret: %s', r.json()['header']['message'])
        elif r.status_code == 406:
            self.logger.error('  invalid Accept header in siret request')
        elif r.status_code == 414:
            self.logger.error('  siret request URI too long')
        # TODO : many errors appear in log file
        else:
            self.logger.error('  error during siret retrieval. Code received : %d', r.status_code)
            if self.debug:
                self.logger.debug('  response %s', r.text)
        exit(1)

    def get_updated_siret_records(self, date):
        # Which fields do we need
        champs = 'siren,nic,siret,complementAdresseEtablissement,numeroVoieEtablissement,indiceRepetitionEtablissement,' \
                 'typeVoieEtablissement,libelleVoieEtablissement,codePostalEtablissement,libelleCedexEtablissement,' \
                 'codeCommuneEtablissement,libelleCommuneEtablissement'

        # Build the filter
        q = 'dateDernierTraitementEtablissement:' + date

        # Retrieve the whole list recursively
        updated_siret_list = list()
        curseur = ''
        curseur_suivant = '*'
        while curseur != curseur_suivant:
            curseur = curseur_suivant
            j = self.get_siret(q=q, curseur=curseur, nombre=10000, gzip=True)
            try:
                header = j['header']
                etablissements = j['etablissements']
                curseur = header['curseur']
                curseur_suivant = header['curseurSuivant']
                updated_siret_list.extend(etablissements)
                # Get header for debugging purposes
                if self.debug:
                    self.logger.debug('  header siret %s', header)
            except KeyError as e:
                self.logger.error('  missing key in response from API: %s', e)
                exit(1)

        return updated_siret_list

    def get_etablissement_siege(self, siren, nic):
        # Which fields do we need
        champs = 'siren,nic,siret,etablissementSiege,codeCommuneEtablissement'

        # Build the filter
        q = 'siret:' + siren + nic

        j = self.get_siret(q=q, champs=champs)
        try:
            header = j['header']
            siret = j['etablissements'][0]
            # Get header for debugging purposes
            if self.debug:
                self.logger.debug('  header siret %s', header)
        except KeyError as e:
            self.logger.error('  missing key in response from API: %s', e)
            exit(1)

        return siret

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in xrange(0, len(l), n):
            yield l[i:i + n]

    def get_etablissements_siege(self, siret_to_retrieve):
        # Which fields do we need
        champs = 'siren,nic,siret,etablissementSiege,codeCommuneEtablissement,codePaysEtrangerEtablissement'

        # Retrieve 85 records at each request
        step = 85
        sieges = dict()
        for chunk in list(self.chunks(siret_to_retrieve, step)):
            q = ''
            for siret in chunk:
                q += 'siret:' + siret + ' OR '
            q = q[:-4]
            j = self.get_siret(q=q, nombre=step, champs=champs, gzip=True)
            try:
                header = j['header']
                for s in j['etablissements']:
                    sieges[s['siret']] = s
                # Get header for debugging purposes
                if self.debug:
                    self.logger.debug('  header siret %s', header)
            except KeyError as e:
                self.logger.error('  missing key in response from API: %s', e)
                exit(1)

        self.logger.info('  retrieved %d of %d headquarters', len(sieges), len(siret_to_retrieve))

        return sieges

    def generate(self):

        self.set_configuration()
        
        # CSV header
        csv_header = ['SIREN', 'NIC', 'L1_NORMALISEE', 'L2_NORMALISEE', 'L3_NORMALISEE', 'L4_NORMALISEE', 'L5_NORMALISEE',
         'L6_NORMALISEE', 'L7_NORMALISEE', 'L1_DECLAREE', 'L2_DECLAREE', 'L3_DECLAREE', 'L4_DECLAREE', 'L5_DECLAREE',
         'L6_DECLAREE', 'L7_DECLAREE', 'NUMVOIE', 'INDREP', 'TYPVOIE', 'LIBVOIE', 'CODPOS', 'CEDEX', 'RPET', 'LIBREG',
         'DEPET', 'ARRONET', 'CTONET', 'COMET', 'LIBCOM', 'DU', 'TU', 'UU', 'EPCI', 'TCD', 'ZEMET', 'SIEGE', 'ENSEIGNE',
         'IND_PUBLIPO', 'DIFFCOM', 'AMINTRET', 'NATETAB', 'LIBNATETAB', 'APET700', 'LIBAPET', 'DAPET', 'TEFET',
         'LIBTEFET', 'EFETCENT', 'DEFET', 'ORIGINE', 'DCRET', 'DDEBACT', 'ACTIVNAT', 'LIEUACT', 'ACTISURF', 'SAISONAT',
         'MODET', 'PRODET', 'PRODPART', 'AUXILT', 'NOMEN_LONG', 'SIGLE', 'NOM', 'PRENOM', 'CIVILITE', 'RNA', 'NICSIEGE',
         'RPEN', 'DEPCOMEN', 'ADR_MAIL', 'NJ', 'LIBNJ', 'APEN700', 'LIBAPEN', 'DAPEN', 'APRM', 'ESS', 'DATEESS',
         'TEFEN', 'LIBTEFEN', 'EFENCENT', 'DEFEN', 'CATEGORIE', 'DCREN', 'AMINTREN', 'MONOACT', 'MODEN', 'PRODEN',
         'ESAANN', 'TCA', 'ESAAPEN', 'ESASEC1N', 'ESASEC2N', 'ESASEC3N', 'ESASEC4N', 'VMAJ', 'VMAJ1', 'VMAJ2', 'VMAJ3',
         'DATEMAJ', 'EVE', 'DATEVE', 'TYPCREH', 'DREACTET', 'DREACTEN', 'MADRESSE', 'MENSEIGNE', 'MAPET', 'MPRODET',
         'MAUXILT', 'MNOMEN', 'MSIGLE', 'MNICSIEGE', 'MNJ', 'MAPEN', 'MPRODEN', 'SIRETPS', 'TEL']

        # https://www.sirene.fr/sirene/public/variable/tefet
        LIBTEFET = {'NN': 'Unités non employeuses',
                    '00': '0 salarié',
                    '01': '1 ou 2 salariés',
                    '02': '3 à 5 salariés',
                    '03': '6 à 9 salariés',
                    '11': '10 à 19 salariés',
                    '12': '20 à 49 salariés',
                    '21': '50 à 99 salariés',
                    '22': '100 à 199 salariés',
                    '31': '200 à 249 salariés',
                    '32': '250 à 499 salariés',
                    '41': '500 à 999 salariés',
                    '42': '1 000 à 1 999 salariés',
                    '51': '2 000 à 4 999 salariés',
                    '52': '5 000 à 9 999 salariés',
                    '53': '10 000 salariés et plus'
        }

        # https://www.sirene.fr/sirene/public/variable/rpen
        RPEN = {'01': ['971'],
                '02': ['972'],
                '03': ['973'],
                '04': ['974'],
                '06': ['976'],
                '07': ['977'],
                '08': ['978'],
                '11': ['75', '77', '78', '91', '92', '93', '94', '95'],
                '24': ['18', '28', '36', '37', '41', '45'],
                '27': ['21', '25', '39', '58', '70', '71', '89', '90'],
                '28': ['14', '27', '50', '61', '76'],
                '32': ['02', '59', '60', '62', '80'],
                '44': ['08', '10', '51', '52', '54', '55', '57', '67', '68', '88'],
                '52': ['44', '49', '53', '72', '85'],
                '53': ['22', '29', '35', '56'],
                '75': ['16', '17', '19', '23', '24', '33', '40', '47', '64', '79', '86', '87'],
                '76': ['09', '11', '12', '30', '31', '32', '34', '46', '48', '65', '66', '81', '82'],
                '84': ['01', '03', '07', '15', '26', '38', '42', '43', '63', '69', '73', '74'],
                '93': ['04', '05', '06', '13', '83', '84'],
                '94': ['2A', '2B'],
                '98': ['975', '984', '986', '987', '988'],
                '99': ['99'],
        }

        # https://www.sirene.fr/sirene/public/variable/depet
        DEPET = {''

        }

        # Get status for debugging purposes
        if self.debug:
            status_object = self.get_status()
            if status_object:
                if 'versionService' in status_object:
                    self.logger.debug('  versionService %s', status_object['versionService'].encode('utf-8'))
                if 'datesDernieresMisesAJourDesDonnees' in status_object:
                    for collection in status_object['datesDernieresMisesAJourDesDonnees']:
                        if 'collection' in collection and collection['collection']:
                            self.logger.debug('  collection %s', collection['collection'].encode('utf-8'))
                        if 'dateDerniereMiseADisposition' in collection and collection['dateDerniereMiseADisposition']:
                            self.logger.debug('  dateDerniereMiseADisposition %s',
                                              collection['dateDerniereMiseADisposition'].encode('utf-8'))
                        if 'dateDernierTraitementDeMasse' in collection and collection['dateDernierTraitementDeMasse']:
                            self.logger.debug('  dateDernierTraitementDeMasse %s',
                                              collection['dateDernierTraitementDeMasse'].encode('utf-8'))
                        if 'dateDernierTraitementMaximum' in collection and collection['dateDernierTraitementMaximum']:
                            self.logger.debug('  dateDernierTraitementMaximum %s',
                                              collection['dateDernierTraitementMaximum'].encode('utf-8'))

        # Date to retrieve has been set
        if self.dtr:
            day_before_yesterday = self.dtr
        # Day before yesterday
        else:
            day_before_yesterday = (date.today() - timedelta(1)).strftime('%Y-%m-%d')

        # Get updated siret records
        updated_siret_list = self.get_updated_siret_records(day_before_yesterday)
        self.logger.info('  retrieved %d siret to update', len(updated_siret_list))

        siret_to_retrieve = list()
        for siret in updated_siret_list:
            if not siret['etablissementSiege']:
                if siret['siren']+siret['uniteLegale']['nicSiegeUniteLegale'] not in siret_to_retrieve:
                    siret_to_retrieve.append(siret['siren']+siret['uniteLegale']['nicSiegeUniteLegale'])

        # We retrieve all headquarters
        siret_siege = self.get_etablissements_siege(siret_to_retrieve)

        event = 1
        count_in = 0
        count_out = 0
        # Parse the list of siret
        for siret in updated_siret_list:
            new_siret = OrderedDict()
            v = lambda t: '' if t is None else t.encode('utf-8')
            try:
                u = siret['uniteLegale']
                a = siret['adresseEtablissement']
                a2 = siret['adresse2Etablissement']
                p = siret['periodesEtablissement'][0]

                new_siret['SIREN'] = v(siret['siren'])
                new_siret['NIC'] = v(siret['nic'])
                # Physical person
                if v(u['categorieJuridiqueUniteLegale']) == '1000':
                    if v(u['sexeUniteLegale']):
                        sul = v(u['sexeUniteLegale'])
                        if sul == 'F':
                            sul = 'MADAME'
                        elif sul == 'M':
                            sul = 'MONSIEUR'
                    if v(u['nomUsageUniteLegale']):
                        nul = v(u['nomUsageUniteLegale'])
                    else:
                        nul = v(u['nomUniteLegale'])
                    puul = v(u['prenomUsuelUniteLegale'])
                    new_siret['L1_NORMALISEE'] = ' '.join(filter(None, [sul, puul, nul]))
                else:
                    new_siret['L1_NORMALISEE'] = v(u['denominationUniteLegale'])
                new_siret['L2_NORMALISEE'] = ''
                nve = v(a['numeroVoieEtablissement'])
                tve = v(a['typeVoieEtablissement'])
                lve = v(a['libelleVoieEtablissement'])
                new_siret['L3_NORMALISEE'] = ' '.join(filter(None, [nve, tve, lve]))
                new_siret['L4_NORMALISEE'] = ''
                new_siret['L5_NORMALISEE'] = ''
                cpe = v(a['codePostalEtablissement'])
                lce = v(a['libelleCommuneEtablissement'])
                new_siret['L6_NORMALISEE'] = ' '.join(filter(None, [cpe, lce]))
                if a['codePaysEtrangerEtablissement'] and a['libellePaysEtrangerEtablissement']:
                    new_siret['L7_NORMALISEE'] = a['libellePaysEtrangerEtablissement'].encode('utf-8')
                else:
                    new_siret['L7_NORMALISEE'] = 'FRANCE'.encode('utf-8')
                new_siret['L1_DECLAREE'] = new_siret['L1_NORMALISEE']
                new_siret['L2_DECLAREE'] = ''
                new_siret['L3_DECLAREE'] = new_siret['L3_NORMALISEE']
                new_siret['L4_DECLAREE'] = ''
                new_siret['L5_DECLAREE'] = ''
                new_siret['L6_DECLAREE'] = ''
                new_siret['L7_DECLAREE'] = new_siret['L7_NORMALISEE']
                new_siret['NUMVOIE'] = v(a['numeroVoieEtablissement'])
                new_siret['INDREP'] = v(a['indiceRepetitionEtablissement'])
                new_siret['TYPVOIE'] = v(a['typeVoieEtablissement'])
                new_siret['LIBVOIE'] = v(a['libelleVoieEtablissement'])
                new_siret['CODPOS'] = v(a['codePostalEtablissement'])
                new_siret['CEDEX'] = v(a['codeCedexEtablissement'])
                new_siret['RPET'] = ''
                new_siret['LIBREG'] = ''
                new_siret['DEPET'] = v(a['codeCommuneEtablissement'])[:2]
                new_siret['ARRONET'] = ''
                new_siret['CTONET'] = ''
                new_siret['COMET'] = v(a['codeCommuneEtablissement'])
                new_siret['LIBCOM'] = v(a['libelleCommuneEtablissement'])
                new_siret['DU'] = ''
                new_siret['TU'] = ''
                new_siret['UU'] = ''
                new_siret['EPCI'] = ''
                new_siret['TCD'] = ''
                new_siret['ZEMET'] = ''
                if siret['etablissementSiege']:
                    new_siret['SIEGE'] = 1
                else:
                    new_siret['SIEGE'] = 0
                new_siret['ENSEIGNE'] = v(p['enseigne1Etablissement'])
                new_siret['IND_PUBLIPO'] = ''
                new_siret['DIFFCOM'] = 'O'.encode('utf-8')
                new_siret['AMINTRET'] = date.today().strftime('%Y%m')
                new_siret['NATETAB'] = ''
                new_siret['LIBNATETAB'] = ''
                new_siret['APET700'] = v(p['activitePrincipaleEtablissement']).replace('.', '')
                new_siret['LIBAPET'] = v(p['activitePrincipaleEtablissement'])
                new_siret['DAPET'] = ''
                new_siret['TEFET'] = v(siret['trancheEffectifsEtablissement'])
                if siret['trancheEffectifsEtablissement']:
                    new_siret['LIBTEFET'] = LIBTEFET[siret['trancheEffectifsEtablissement']]
                else:
                    new_siret['LIBTEFET'] = ''
                new_siret['EFETCENT'] = ''
                new_siret['DEFET'] = v(siret['anneeEffectifsEtablissement'])
                new_siret['ORIGINE'] = ''
                new_siret['DCRET'] = v(siret['dateCreationEtablissement']).replace('-', '')
                new_siret['DDEBACT'] = ''
                new_siret['ACTIVNAT'] = ''
                new_siret['LIEUACT'] = ''
                new_siret['ACTISURF'] = ''
                new_siret['SAISONAT'] = ''
                new_siret['MODET'] = ''
                new_siret['PRODET'] = ''
                new_siret['PRODPART'] = ''
                new_siret['AUXILT'] = ''
                # Physical person
                if v(u['categorieJuridiqueUniteLegale']) == '1000':
                    nul = v(u['nomUniteLegale'])
                    p1ul = v(u['prenom1UniteLegale'])
                    p2ul = v(u['prenom2UniteLegale'])
                    p3ul = v(u['prenom3UniteLegale'])
                    p4ul = v(u['prenom4UniteLegale'])
                    pul = ' '.join(filter(None, [p1ul, p2ul, p3ul, p4ul]))
                    if v(u['nomUsageUniteLegale']):
                        new_siret['NOMEN_LONG'] = nul + '*' + v(u['nomUsageUniteLegale']) + '/' + pul + '/'
                    else:
                        new_siret['NOMEN_LONG'] = nul + '*' + pul + '/'
                else:
                    new_siret['NOMEN_LONG'] = v(u['denominationUniteLegale'])
                new_siret['SIGLE'] = v(u['sigleUniteLegale'])
                new_siret['NOM'] = v(u['nomUniteLegale'])
                new_siret['PRENOM'] = v(u['prenom1UniteLegale'])
                new_siret['CIVILITE'] = ''
                if v(u['sexeUniteLegale']) == 'F':
                    new_siret['CIVILITE'] = 2
                elif v(u['sexeUniteLegale']) == 'M':
                    new_siret['CIVILITE'] = 1
                new_siret['RNA'] = v(u['identifiantAssociationUniteLegale'])
                new_siret['NICSIEGE'] = v(u['nicSiegeUniteLegale'])
                if siret['etablissementSiege']:
                    if v(a['codePaysEtrangerEtablissement']):
                        cce = v(a['codePaysEtrangerEtablissement'])
                    else:
                        cce = v(a['codeCommuneEtablissement'])
                    department = cce[:3]
                    rpen = ''
                    for key, value in RPEN.items():
                        if department in value:
                            rpen = key
                    if rpen == '':
                        department = cce[:2]
                        for key, value in RPEN.items():
                            if department in value:
                                rpen = key
                else:
                    rpen = ''
                    try:
                        siege = siret_siege[v(siret['siren'])+v(u['nicSiegeUniteLegale'])]
                    except KeyError as e:
                        self.logger.info('  siret %s has an invalid headquarter %s', \
                                          v(siret['siret']), v(siret['siren']) + v(u['nicSiegeUniteLegale']))
                    else:
                        if v(siege['adresseEtablissement']['codePaysEtrangerEtablissement']):
                            cce = v(siege['adresseEtablissement']['codePaysEtrangerEtablissement'])
                        else:
                            cce = v(siege['adresseEtablissement']['codeCommuneEtablissement'])
                        department = cce[:3]
                        rpen = ''
                        for key, value in RPEN.items():
                            if department in value:
                                rpen = key
                        if rpen == '':
                            department = cce[:2]
                            for key, value in RPEN.items():
                                if department in value:
                                    rpen = key
                new_siret['RPEN'] = rpen
                new_siret['DEPCOMEN'] = cce
                new_siret['ADR_MAIL'] = ''
                new_siret['NJ'] = v(u['categorieJuridiqueUniteLegale'])
                new_siret['LIBNJ'] = v(u['categorieJuridiqueUniteLegale'])
                new_siret['APEN700'] = v(u['activitePrincipaleUniteLegale']).replace('.', '')
                new_siret['LIBAPEN'] = v(u['activitePrincipaleUniteLegale'])
                new_siret['DAPEN'] = ''
                new_siret['APRM'] = v(siret['activitePrincipaleRegistreMetiersEtablissement'])
                new_siret['ESS'] = v(u['economieSocialeSolidaireUniteLegale'])
                new_siret['DATEESS'] = ''
                new_siret['TEFEN'] = v(u['trancheEffectifsUniteLegale'])
                if u['trancheEffectifsUniteLegale']:
                    new_siret['LIBTEFEN'] = LIBTEFET[u['trancheEffectifsUniteLegale']]
                else:
                    new_siret['LIBTEFEN'] = ''
                new_siret['EFENCENT'] = ''
                new_siret['DEFEN'] = v(u['anneeEffectifsUniteLegale'])
                new_siret['CATEGORIE'] = v(u['categorieEntreprise'])
                new_siret['DCREN'] = v(u['dateCreationUniteLegale'])
                new_siret['AMINTREN'] = date.today().strftime('%Y%m')
                new_siret['MONOACT'] = ''
                new_siret['MODEN'] = ''
                new_siret['PRODEN'] = ''
                new_siret['ESAANN'] = ''
                new_siret['TCA'] = ''
                new_siret['ESAAPEN'] = ''
                new_siret['ESASEC1N'] = ''
                new_siret['ESASEC2N'] = ''
                new_siret['ESASEC3N'] = ''
                new_siret['ESASEC4N'] = ''
                if v(p['etatAdministratifEtablissement']) == 'A':
                    new_siret['VMAJ'] = 'C'
                    count_in += 1
                elif v(p['etatAdministratifEtablissement']) == 'F':
                    new_siret['VMAJ'] = 'O'
                    count_out += 1
                new_siret['VMAJ1'] = ''
                new_siret['VMAJ2'] = ''
                new_siret['VMAJ3'] = ''
                new_siret['DATEMAJ'] = v(siret['dateDernierTraitementEtablissement'])
                if v(p['etatAdministratifEtablissement']) == 'A':
                    new_siret['EVE'] = 'CE'
                elif v(p['etatAdministratifEtablissement']) == 'F':
                    new_siret['EVE'] = 'O'
                new_siret['DATEVE'] = v(siret['dateDernierTraitementEtablissement'])[:10].replace('-', '')
                new_siret['TYPCREH'] = ''
                new_siret['DREACTET'] = ''
                new_siret['DREACTEN'] = ''
                new_siret['MADRESSE'] = ''
                new_siret['MENSEIGNE'] = ''
                new_siret['MAPET'] = ''
                new_siret['MPRODET'] = ''
                new_siret['MAUXILT'] = ''
                new_siret['MNOMEN'] = ''
                new_siret['MSIGLE'] = ''
                new_siret['MNICSIEGE'] = ''
                new_siret['MNJ'] = ''
                new_siret['MAPEN'] = ''
                new_siret['MPRODEN'] = ''
                new_siret['SIRETPS'] = ''
                new_siret['TEL'] = ''
            # TODO : too much errors are coming from there
            except KeyError as e:
                self.logger.error('  missing key in siret received from API: %s', e)
                if self.debug:
                    self.logger.debug('  siret to update: %s', siret)
                    self.logger.debug('  new_siret object: %s', new_siret)
                exit(1)
            
            raw = ''.join(k+'='+'\"{0}\"'.format(v)+' ' for k, v in new_siret.items())
            event += 1
            yield {'_time': time.time(), 'event_no': event, '_raw': raw}
        self.logger.info('  generated %d events', event-1)
        self.logger.info('  found %d SIRET to create', count_in)
        self.logger.info('  found %d SIRET to delete', count_out)

dispatch(INSEECommand, sys.argv, sys.stdin, sys.stdout, __name__)
