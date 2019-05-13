#!/usr/bin/env python

import sys
from splunklib import six
from splunklib.searchcommands import dispatch, ReportingCommand, Configuration, Option, validators
import os
from datetime import date, timedelta, datetime
import json


class Date(validators.Validator):
    """ Validates Date option values.

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


@Configuration(run_in_preview=False, requires_preop=False)
class XL2Command(ReportingCommand):
    """ Synopsis

    ##Syntax

    xl2

    ##Description

    This command writes events to CSV file

    """
    dtr = Option(require=False, validate=Date())

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
        if 'csv_folder' not in conf:
            self.logger.error('  CSV folder is not defined in the configuration file')

        self.csv_folder = conf['csv_folder']

    @Configuration()
    def map(self, records):
        return records

    def reduce(self, events):

        self.set_configuration()

        # splunk_home = os.environ['SPLUNK_HOME']

        if self.dtr:
            filename = self.dtr + '_' + datetime.now().strftime('%Y%m%d%H%M%S')
        else:
            filename = (date.today() - timedelta(1)).strftime('%Y-%m-%d') + '_' + \
                       datetime.now().strftime('%Y%m%d%H%M%S')

        header = ('"SIREN";"NIC";"L1_NORMALISEE";"L2_NORMALISEE";"L3_NORMALISEE";"L4_NORMALISEE";"L5_NORMALISEE";'
                  '"L6_NORMALISEE";"L7_NORMALISEE";"L1_DECLAREE";"L2_DECLAREE";"L3_DECLAREE";"L4_DECLAREE";'
                  '"L5_DECLAREE";"L6_DECLAREE";"L7_DECLAREE";"NUMVOIE";"INDREP";"TYPVOIE";"LIBVOIE";"CODPOS";"CEDEX"'
                  ';"RPET";"LIBREG";"DEPET";"ARRONET";"CTONET";"COMET";"LIBCOM";"DU";"TU";"UU";"EPCI";"TCD";"ZEMET";'
                  '"SIEGE";"ENSEIGNE";"IND_PUBLIPO";"DIFFCOM";"AMINTRET";"NATETAB";"LIBNATETAB";"APET700";"LIBAPET";'
                  '"DAPET";"TEFET";"LIBTEFET";"EFETCENT";"DEFET";"ORIGINE";"DCRET";"DDEBACT";"ACTIVNAT";"LIEUACT";'
                  '"ACTISURF";"SAISONAT";"MODET";"PRODET";"PRODPART";"AUXILT";"NOMEN_LONG";"SIGLE";"NOM";"PRENOM";'
                  '"CIVILITE";"RNA";"NICSIEGE";"RPEN";"DEPCOMEN";"ADR_MAIL";"NJ";"LIBNJ";"APEN700";"LIBAPEN";"DAPEN"'
                  ';"APRM";"ESS";"DATEESS";"TEFEN";"LIBTEFEN";"EFENCENT";"DEFEN";"CATEGORIE";"DCREN";"AMINTREN";'
                  '"MONOACT";"MODEN";"PRODEN";"ESAANN";"TCA";"ESAAPEN";"ESASEC1N";"ESASEC2N";"ESASEC3N";"ESASEC4N";'
                  '"VMAJ";"VMAJ1";"VMAJ2";"VMAJ3";"DATEMAJ";"EVE";"DATEVE";"TYPCREH";"DREACTET";"DREACTEN";'
                  '"MADRESSE";"MENSEIGNE";"MAPET";"MPRODET";"MAUXILT";"MNOMEN";"MSIGLE";"MNICSIEGE";"MNJ";"MAPEN";'
                  '"MPRODEN";"SIRETPS";"TEL"\n')

        header_written = False

        for event in events:
            with open(os.path.join(self.csv_folder, 'sirc-%s.csv' % filename), 'a') as fd:
                if not header_written:
                    fd.write(header)
                    header_written = True

                row = {}
                first = True
                for f, v in event.items():
                    if not first:
                        fd.write(';')
                    fd.write('"' + v + '"')
                    row[f] = v
                    first = False
                fd.write('\n')
                yield row


dispatch(XL2Command, sys.argv, sys.stdin, sys.stdout, __name__)
