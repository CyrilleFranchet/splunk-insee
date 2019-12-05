#!/usr/bin/env python

import sys
from splunklib import six
from splunklib.searchcommands import dispatch, ReportingCommand, Configuration, Option, validators
import os
from datetime import date, timedelta, datetime
import stat
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import time
try:
    import zlib
    compression = ZIP_DEFLATED
except:
    compression = ZIP_STORED


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


@Configuration(requires_preop=True, run_in_preview=False)
class XL2Command(ReportingCommand):
    """ Synopsis

    ##Syntax

    xl2

    ##Description

    This command writes events to CSV file

    """
    dtr = Option(require=False, validate=Date())
    header = ['SIREN','NIC','L1_NORMALISEE','L2_NORMALISEE','L3_NORMALISEE','L4_NORMALISEE','L5_NORMALISEE',
              'L6_NORMALISEE','L7_NORMALISEE','L1_DECLAREE','L2_DECLAREE','L3_DECLAREE','L4_DECLAREE',
              'L5_DECLAREE','L6_DECLAREE','L7_DECLAREE','NUMVOIE','INDREP','TYPVOIE','LIBVOIE','CODPOS','CEDEX',
              'RPET','LIBREG','DEPET','ARRONET','CTONET','COMET','LIBCOM','DU','TU','UU','EPCI','TCD','ZEMET',
              'SIEGE','ENSEIGNE','IND_PUBLIPO','DIFFCOM','AMINTRET','NATETAB','LIBNATETAB','APET700','LIBAPET',
              'DAPET','TEFET','LIBTEFET','EFETCENT','DEFET','ORIGINE','DCRET','DDEBACT','ACTIVNAT','LIEUACT',
              'ACTISURF','SAISONAT','MODET','PRODET','PRODPART','AUXILT','NOMEN_LONG','SIGLE','NOM','PRENOM',
              'CIVILITE','RNA','NICSIEGE','RPEN','DEPCOMEN','ADR_MAIL','NJ','LIBNJ','APEN700','LIBAPEN','DAPEN',
              'APRM','ESS','DATEESS','TEFEN','LIBTEFEN','EFENCENT','DEFEN','CATEGORIE','DCREN','AMINTREN',
              'MONOACT','MODEN','PRODEN','ESAANN','TCA','ESAAPEN','ESASEC1N','ESASEC2N','ESASEC3N','ESASEC4N',
              'VMAJ','VMAJ1','VMAJ2','VMAJ3','DATEMAJ','EVE','DATEVE','TYPCREH','DREACTET','DREACTEN',
              'MADRESSE','MENSEIGNE','MAPET','MPRODET','MAUXILT','MNOMEN','MSIGLE','MNICSIEGE','MNJ','MAPEN',
              'MPRODEN','SIRETPS','TEL']

    def return_header(self):
        return ''.join(map(lambda x: '"%s";' % x, self.header))[:-1]

    @Configuration()
    def map(self, events):
        try:
            if self.dtr:
                filename = self.dtr + '_'
            else:
                filename = (date.today() - timedelta(1)).strftime('%Y-%m-%d') + '_'

            csv_filename = '/data_out/insee/sirc-%s.csv' % filename

            for event in events:
                with open(csv_filename, 'a') as fd:
                    first = True
                    for e in self.header:
                        if not first:
                            fd.write(';')
                        fd.write('"' + event[e] + '"')
                        first = False
                    fd.write('\n')
                    fd.flush()

        # This is a bad practise, but we want a specific message in log file
        # This case means that the code is missing an Exception handling
        except Exception as e:
            self.logger.error('  unhandled exception has occurred. Traceback is in splunklib.log: %s', e.message)
            raise

        yield {'dummy': 0}

    def reduce(self, records):
        zip_filename = 'Not ZIP file generated. Error during creation.'
        counter = 0
        try:
            if self.dtr:
                filename = self.dtr + '_' + datetime.now().strftime('%Y%m%d%H%M%S')
                old_filename = self.dtr + '_'
            else:
                filename = (date.today() - timedelta(1)).strftime('%Y-%m-%d') + '_' + \
                           datetime.now().strftime('%Y%m%d%H%M%S')
                old_filename = (date.today() - timedelta(1)).strftime('%Y-%m-%d') + '_'
            csv_filename = '/data_out/insee/sirc-%s.csv' % filename
            old_csv_filename = '/data_out/insee/sirc-%s.csv' % old_filename

            for _ in records:
                if os.path.exists(old_csv_filename):
                    with open(old_csv_filename, 'r') as fin:
                        with open(csv_filename, 'w') as fout:
                            fout.write(self.return_header())
                            fout.write('\n')
                            for line in fin.readlines():
                                fout.write(line)
                                counter += 1

                    time.sleep(1)

                    # Delete the first CSV file
                    if os.path.exists(old_csv_filename):
                        os.remove(old_csv_filename)

                    if self.dtr:
                        zip_filename = '/data_out/insee/' + 'sirene_' + ''.join(self.dtr.split('-')) + '.zip'
                    else:
                        zip_filename = '/data_out/insee/' + 'sirene_' + (date.today() - timedelta(1)).strftime('%Y%m%d') + '.zip'

                    if os.path.exists(csv_filename):
                        # ZIP the file
                        with ZipFile(zip_filename, mode='w', compression=compression, allowZip64=True) as zip_file:
                            zip_file.write(csv_filename, arcname='sirc-%s.csv' % filename)

                        time.sleep(1)

                        # Give RW to the UNIX group
                        os.chmod(zip_filename, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)

                        # Delete the CSV file
                        os.remove(csv_filename)

        # This is a bad practise, but we want a specific message in log file
        # This case means that the code is missing an Exception handling
        except Exception as e:
            self.logger.error('  unhandled exception has occurred. Traceback is in splunklib.log: %s', e.message)
            raise

        yield {'file': zip_filename, 'records': counter}


dispatch(XL2Command, sys.argv, sys.stdin, sys.stdout, __name__)
