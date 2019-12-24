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


class ExceptionStatus(Exception):
    pass


class ExceptionToken(Exception):
    pass


class ExceptionConfiguration(Exception):
    pass


class ExceptionSiret(Exception):
    pass


class ExceptionUpdatedSiret(Exception):
    pass


class ExceptionHeadquarters(Exception):
    pass


class ExceptionTranslation(Exception):
    pass


class ExceptionDateParameter(Exception):
    pass


@Configuration(type='events')
class PNAFCommand(GeneratingCommand):
    """ Synopsis

    ##Syntax

    | pnaf [proxy=true] [debug=true]

    ##Description

    Request the Sirene API for the prospect

    """
    debug = Option(require=False, validate=validators.Boolean())
    proxy = Option(require=False, validate=validators.Boolean())

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

    count_in = 0
    count_out = 0

    def set_configuration(self):
        # Open the configuration file
        try:
            with open(os.path.dirname(os.path.abspath(__file__)) + '/configuration_json.txt', 'r') as conf_file:
                conf = json.load(conf_file)
        except ValueError:
            self.logger.error('  invalid JSON configuration file')
            raise ExceptionConfiguration('Invalid JSON in the configuration file')
        except IOError:
            self.logger.error('  configuration file doesn\'t exist')
            raise ExceptionConfiguration('Missing configuration file')

        # Verify the configuration
        if self.proxy:
            if 'http_proxy' not in conf or 'https_proxy' not in conf:
                self.logger.error('  proxies are not defined in the configuration file')
                raise ExceptionConfiguration('Proxies are not defined in the configuration file')
            self.proxies = dict()
            self.proxies['http'] = conf['http_proxy']
            self.proxies['https'] = conf['https_proxy']

        if 'consumer_key' not in conf or 'consumer_secret' not in conf:
            self.logger.error('  API credentials are not defined in the configuration file')
            raise ExceptionConfiguration('Missing API credentials in the configuration file')

        if 'prospects' not in conf:
            self.logger.error('  Prospects NAF are not defined in the configuration file')
            raise ExceptionConfiguration('Missing NAF codes in the configuration file')

        if 'endpoint_token' not in conf or 'endpoint_etablissement' not in conf or 'endpoint_informations' not in conf:
            self.logger.error('  API endpoints are not defined in the configuration file')
            raise ExceptionConfiguration('Missing API endpoints in the configuration file')

        self.consumer_key = conf['consumer_key']
        self.consumer_secret = conf['consumer_secret']
        self.endpoint_token = conf['endpoint_token']
        self.endpoint_etablissement = conf['endpoint_etablissement']
        self.endpoint_informations = conf['endpoint_informations']
        self.prospects = conf['prospects']
        self.bearer_token = self.get_api_token()

    def get_api_token(self):
        payload = {'grant_type': 'client_credentials'}
        basic_auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        if self.proxy:
            r = requests.post(self.endpoint_token, auth=basic_auth, data=payload, proxies=self.proxies)
        else:
            r = requests.post(self.endpoint_token, auth=basic_auth, data=payload)

        if self.debug:
            self.logger.debug('  token response %s\n%s', r.headers, r.text)

        if r.headers['Content-Type'] and 'application/json' in r.headers['Content-Type']:
            if r.status_code == 200:
                return r.json()['access_token']
            elif r.status_code == 401:
                self.logger.error('  incorrect credentials : %s', r.json()['error_description'])
            else:
                self.logger.error('  error during token retrieval. Code received : %d', r.status_code)
        else:
            self.logger.error('  error during token retrieval. Code received : %d', r.status_code)
        raise ExceptionToken('Error during API token retrieval')

    def get_status(self):
        # Initialize
        headers = {'Authorization': 'Bearer ' + self.bearer_token}

        if self.proxy:
            r = requests.get(self.endpoint_informations, headers=headers,
                             proxies=self.proxies)
        else:
            r = requests.get(self.endpoint_informations, headers=headers)

        if self.debug:
            self.logger.debug('  status response %s\n%s', r.headers, r.text)

        while r.status_code == 429:
            # We made too many requests. We wait for the next rounded minute
            current_second = datetime.now().time().strftime('%S')
            time.sleep(60 - int(current_second) + 1)
            if self.proxy:
                r = requests.get(self.endpoint_informations, headers=headers,
                                 proxies=self.proxies)
            else:
                r = requests.get(self.endpoint_informations, headers=headers)
            if self.debug:
                self.logger.debug('  status response %s\n%s', r.headers, r.text)

        if r.headers['Content-Type'] and 'application/json' in r.headers['Content-Type']:
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 401:
                self.logger.error('  invalid bearer token %s in status request', self.bearer_token)
            elif r.status_code == 406:
                self.logger.error('  invalid Accept header in status request')
            else:
                self.logger.error('  error during status retrieval. Code received : %d', r.status_code)
        else:
            self.logger.error('  error during status retrieval. Code received : %d', r.status_code)
        raise ExceptionStatus('Error during information retrieval')

    def post_siret(self, q=None, nombre=None, curseur=None, champs=None, date=None, gzip=False):
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
        if date:
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                raise ExceptionDateParameter('Unrecognized date parameter: {0}. Should be AAAA-MM-JJ'.format(date))
            payload['date'] = date

        headers = {'Authorization': 'Bearer ' + self.bearer_token}

        if gzip:
            # Request GZip content
            headers['Accept-Encoding'] = 'gzip'

        if self.proxy:
            r = requests.post(self.endpoint_etablissement, headers=headers, data=payload, proxies=self.proxies)
        else:
            r = requests.post(self.endpoint_etablissement, headers=headers, data=payload)

        if self.debug:
            self.logger.debug('  POST siret response %s\n%s', r.headers, r.text)

        while r.status_code == 429:
            # We made too many requests. We wait for the next rounded minute
            current_second = datetime.now().time().strftime('%S')
            time.sleep(60 - int(current_second) + 1)
            if self.proxy:
                r = requests.post(self.endpoint_etablissement, headers=headers, data=payload, proxies=self.proxies)
            else:
                r = requests.post(self.endpoint_etablissement, headers=headers, data=payload)
            if self.debug:
                self.logger.debug('  POST siret response %s\n%s', r.headers, r.text)

        internal_error_counter = 0
        while r.status_code == 500:
            # In case we get a 500 we prefer to retry our request before raising an error
            internal_error_counter += 1
            time.sleep(60)
            if self.proxy:
                r = requests.post(self.endpoint_etablissement, headers=headers, data=payload, proxies=self.proxies)
            else:
                r = requests.post(self.endpoint_etablissement, headers=headers, data=payload)
            if self.debug:
                self.logger.debug('  POST siret response %s\n%s', r.headers, r.text)
            if internal_error_counter == 10:
                break

        if r.headers['Content-Type'] and 'application/json' in r.headers['Content-Type']:
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 400:
                self.logger.error('  invalid parameters in POST query: %s', r.json()['header']['message'])
            elif r.status_code == 401:
                self.logger.error('  invalid bearer token %s in siret POST request', self.bearer_token)
            elif r.status_code == 404:
                self.logger.error('  POST unknown siret: %s', r.json()['header']['message'])
            elif r.status_code == 406:
                self.logger.error('  invalid Accept header in siret POST request')
            elif r.status_code == 414:
                self.logger.error('  siret POST request URI too long')
            else:
                self.logger.error('  error during siret POST retrieval. Code received : %d', r.status_code)
        else:
            self.logger.error('  error during siret POST retrieval. Code received : %d', r.status_code)

        raise ExceptionSiret('Error during siret POST retrieval')

    def get_siret(self, q=None, nombre=None, curseur=None, champs=None, date=None, gzip=False):
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
        if date:
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                raise ExceptionDateParameter('Unrecognized date parameter: {0}. Should be AAAA-MM-JJ'.format(date))
            payload['date'] = date

        headers = {'Authorization': 'Bearer ' + self.bearer_token}

        if gzip:
            # Request GZip content
            headers['Accept-Encoding'] = 'gzip'

        if self.proxy:
            r = requests.get(self.endpoint_etablissement, headers=headers, params=payload,
                             proxies=self.proxies)
        else:
            r = requests.get(self.endpoint_etablissement, headers=headers, params=payload)

        if self.debug:
            self.logger.debug('  GET siret response %s\n%s', r.headers, r.text)

        while r.status_code == 429:
            # We made too many requests. We wait for the next rounded minute
            current_second = datetime.now().time().strftime('%S')
            time.sleep(60 - int(current_second) + 1)
            if self.proxy:
                r = requests.get(self.endpoint_etablissement, headers=headers, params=payload,
                                 proxies=self.proxies)
            else:
                r = requests.get(self.endpoint_etablissement, headers=headers, params=payload)
            if self.debug:
                self.logger.debug('  GET siret response %s\n%s', r.headers, r.text)

        internal_error_counter = 0
        while r.status_code == 500:
            # In case we get a 500 we prefer to retry our request before raising an error
            internal_error_counter += 1
            time.sleep(60)
            if self.proxy:
                r = requests.get(self.endpoint_etablissement, headers=headers, params=payload,
                                 proxies=self.proxies)
            else:
                r = requests.get(self.endpoint_etablissement, headers=headers, params=payload)
            if self.debug:
                self.logger.debug('  GET siret response %s\n%s', r.headers, r.text)
            if internal_error_counter == 10:
                break

        if r.headers['Content-Type'] and 'application/json' in r.headers['Content-Type']:
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 400:
                self.logger.error('  invalid parameters in GET query: %s', r.json()['header']['message'])
            elif r.status_code == 401:
                self.logger.error('  invalid bearer token %s in siret GET request', self.bearer_token)
            elif r.status_code == 404:
                self.logger.error('  GET unknown siret: %s', r.json()['header']['message'])
            elif r.status_code == 406:
                self.logger.error('  invalid Accept header in siret GET request')
            elif r.status_code == 414:
                self.logger.error('  siret GET request URI too long')
            else:
                self.logger.error('  error during siret GET retrieval. Code received : %d', r.status_code)
        else:
            self.logger.error('  error during siret GET retrieval. Code received : %d', r.status_code)

        raise ExceptionSiret('Error during siret GET retrieval')

    def get_prospects(self, curseur):
        # Which fields do we need
        champs = 'siren,nic,siret,complementAdresseEtablissement,numeroVoieEtablissement,indiceRepetitionEtablissement,' \
                 'typeVoieEtablissement,libelleVoieEtablissement,codePostalEtablissement,libelleCedexEtablissement,' \
                 'codeCommuneEtablissement,libelleCommuneEtablissement'

        # Build the filter
        naf = ''
        for prospect in self.prospects:
            naf += 'activitePrincipaleEtablissement:' + prospect + ' OR '
        q = 'periode(etatAdministratifEtablissement:A AND (' + naf[:-4] + '))'

        j = self.post_siret(q=q, curseur=curseur, nombre=1000, date=date.today().strftime('%Y-%m-%d'), gzip=True)
        try:
            header = j['header']
            etablissements = j['etablissements']
            curseur_suivant = header['curseurSuivant']
            total = header['total']
            # Get header for debugging purposes
            if self.debug:
                self.logger.debug('  header siret %s', header)
        except KeyError as e:
            self.logger.error('  missing key in response from API: %s', e)
            raise ExceptionUpdatedSiret('Error during headquarters retrieval')

        return total, curseur_suivant, etablissements

    def get_updated_siret_records(self, date, curseur):
        # Which fields do we need
        champs = 'siren,nic,siret,complementAdresseEtablissement,numeroVoieEtablissement,indiceRepetitionEtablissement,' \
                 'typeVoieEtablissement,libelleVoieEtablissement,codePostalEtablissement,libelleCedexEtablissement,' \
                 'codeCommuneEtablissement,libelleCommuneEtablissement'

        # Build the filter
        q = 'dateDernierTraitementEtablissement:' + date

        j = self.get_siret(q=q, curseur=curseur, nombre=1000, gzip=True)
        try:
            header = j['header']
            etablissements = j['etablissements']
            curseur_suivant = header['curseurSuivant']
            total = header['total']
            # Get header for debugging purposes
            if self.debug:
                self.logger.debug('  header siret %s', header)
        except KeyError as e:
            self.logger.error('  missing key in response from API: %s', e)
            raise ExceptionUpdatedSiret('Error during headquarters retrieval')

        return total, curseur_suivant, etablissements

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in xrange(0, len(l), n):
            yield l[i:i + n]

    def get_etablissements_siege(self, siret_to_retrieve):
        # Which fields do we need
        champs = 'siren,nic,siret,etablissementSiege,codeCommuneEtablissement,codePaysEtrangerEtablissement'

        # Retrieve 85 records at each request
        # If we have more than 85 siret, the query is too long and blocked by INSEE
        step = 85
        sieges = dict()
        for chunk in list(self.chunks(siret_to_retrieve, step)):
            q = ''
            for siret in chunk:
                q += 'siret:' + siret + ' OR '
            q = q[:-4]
            try:
                j = self.get_siret(q=q, nombre=step, champs=champs, gzip=True)
            except ExceptionSiret:
                continue
            try:
                header = j['header']
                for s in j['etablissements']:
                    sieges[s['siret']] = s
                # Get header for debugging purposes
                if self.debug:
                    self.logger.debug('  header siret %s', header)
            except KeyError as e:
                self.logger.error('  missing key in response from API: %s', e)
                raise ExceptionHeadquarters('Error during headquarters retrieval')

        self.logger.info('  retrieved %d of %d headquarters', len(sieges), len(siret_to_retrieve))

        return sieges

    def generate_siret(self, siret):
        new_siret = OrderedDict()
        v = lambda t: '' if t is None else t.encode('utf-8')
        try:
            u = siret['uniteLegale']
            a = siret['adresseEtablissement']
            # This field is unused
            a2 = siret['adresse2Etablissement']
            p = siret['periodesEtablissement'][0]

            new_siret['Code_INSEE_Commune'] = v(a['codeCommuneEtablissement'])
            new_siret['Code_NAF'] = v(p['activitePrincipaleEtablissement']).replace('.', '')
            new_siret['Libellé_NAF'] = v(p['activitePrincipaleEtablissement'])
            new_siret['Code_postal'] = v(a['codePostalEtablissement'])
            new_siret['No_Siren'] = v(siret['siren'])
            new_siret['Connu_Siren'] = ''
            new_siret['No_Siret'] = v(siret['siret'])
            new_siret['Connu_Siret'] = ''
            new_siret['Date_de_création_établissement'] = datetime.strptime(v(siret['dateCreationEtablissement']),
                                                                            '%Y-%m-%d').strftime('%d/%m/%Y')
            # Physical person
            sul = None
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
                new_siret['Raison_sociale'] = ' '.join(filter(None, [sul, puul, nul]))
            else:
                new_siret['Raison_sociale'] = v(u['denominationUniteLegale'])
            new_siret['Enseigne'] = v(p['enseigne1Etablissement'])
            new_siret['Nom_Prénom'] = v(u['nomUniteLegale']) + ' ' + v(u['prenom1UniteLegale'])
            new_siret['Adresse_postale'] = v(a['numeroVoieEtablissement']) + ' ' + v(a['typeVoieEtablissement']) +\
                                           ' ' + v(a['libelleVoieEtablissement'])
            new_siret['Complément_Adresse'] = v(a['complementAdresseEtablissement'])
            new_siret['Ville'] = v(a['libelleCommuneEtablissement'])
            new_siret['No_Tél'] = ''
            new_siret['Statut_diffusion'] = 'O'.encode('utf-8')

        except KeyError as e:
            self.logger.error('  missing key in siret received from API: %s', e)
            if self.debug:
                self.logger.debug('  siret to update: %s', siret)
                self.logger.debug('  new_siret object: %s', new_siret)
            raise ExceptionTranslation('Error during siret translation')

        raw = ''.join(k + '=' + '\"{0}\"'.format(v) + ' ' for k, v in new_siret.items())
        return raw

    def generate(self):
        try:
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

            # Get status
            status_object = self.get_status()
            if status_object:
                if 'versionService' in status_object:
                    self.logger.info('  versionService %s', status_object['versionService'].encode('utf-8'))
                if 'datesDernieresMisesAJourDesDonnees' in status_object:
                    for collection in status_object['datesDernieresMisesAJourDesDonnees']:
                        msg = ''
                        if 'collection' in collection and collection['collection']:
                            msg += 'collection %s' % collection['collection'].encode('utf-8')
                            msg += ' '
                        if 'dateDerniereMiseADisposition' in collection and collection['dateDerniereMiseADisposition']:
                            msg += 'dateDerniereMiseADisposition %s' %\
                                   collection['dateDerniereMiseADisposition'].encode('utf-8')
                            msg += ' '
                        if 'dateDernierTraitementDeMasse' in collection and collection['dateDernierTraitementDeMasse']:
                            msg += 'dateDernierTraitementDeMasse %s' %\
                                   collection['dateDernierTraitementDeMasse'].encode('utf-8')
                            msg += ' '
                        if 'dateDernierTraitementMaximum' in collection and collection['dateDernierTraitementMaximum']:
                            msg += 'dateDernierTraitementMaximum %s' % \
                                   collection['dateDernierTraitementMaximum'].encode('utf-8')
                            msg += ' '
                        self.logger.info('  %s', msg.encode('utf-8'))

            # Log the username to help debugging
            self.logger.info('  Splunk username: %s', self._metadata.searchinfo.username.encode('utf-8'))

            event = 1
            curseur = '*'
            first_call = True
            received_siret = 0
            while True:
                _, curseur_suivant, updated_siret_list = self.get_prospects(curseur)

                if first_call:
                    self.logger.info('  retrieved a total of %d prospect siret', _)
                    first_call = False
                self.logger.info('  retrieved %d prospect siret in this window', len(updated_siret_list))
                received_siret += len(updated_siret_list)
                self.logger.info('  retrieved %d siret / %d', received_siret, _)

                for siret in updated_siret_list:
                    raw_data = self.generate_siret(siret)
                    yield {'_time': time.time(), 'event_no': event, '_raw': raw_data}
                    event += 1

                # We get the same curseur so we get all updated siret
                if curseur_suivant == curseur:
                    break

                curseur = curseur_suivant

            self.logger.info('  generated %d events', event-1)

        except (ExceptionTranslation, ExceptionHeadquarters, ExceptionUpdatedSiret, ExceptionSiret, ExceptionStatus,
                ExceptionToken, ExceptionConfiguration):
            raise

        # This is a bad practise, but we want a specific message in log file
        # This case means that the code is missing an Exception handling
        except Exception as e:
            self.logger.error('  unhandled exception has occurred. Traceback is in splunklib.log: %s', e.message)
            raise


dispatch(PNAFCommand, sys.argv, sys.stdin, sys.stdout, __name__)
