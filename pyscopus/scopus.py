# -*- coding: utf-8 -*-
import APIURI
import numpy as np
import pandas as pd
from datetime import date
import os, io, warnings, csv, requests
from utils import _parse_author, _parse_author_retrieval,\
        _parse_affiliation, _parse_entry, _parse_citation

'''
    03/03/2017:
    Rewriting the whole class by request package
    Use pandas.DataFrame and numpy.ndAarray all the time.
'''

class Scopus(object):

    '''
        Scopus class.
        For instantiation of scopus objects to retrieve data from scopus.com
        Refer to http://zhiyzuo.github.com/python-scopus for more information
        Let me know if there's any issue with this code.

        Happy coding,
        Zhiya
        zhiyazuo@gmail.com
    '''

    def __init__(self, apikey=None):
        self.apikey = apikey

    def add_key(self, apikey):
        self.apikey = apikey

    def search(self, query, count=100):
        '''
            Returns a list of document records in the form of pandas.DataFrame.

            Search for documents matching the keywords in query
            Details: http://api.elsevier.com/documentation/SCOPUSSearchAPI.wadl
            Tips: http://api.elsevier.com/documentation/search/SCOPUSSearchTips.htm

            Parameters
            ----------------------------------------------------------------------
            query : str
                Query style (see above websites).
            count : int
                The number of records to be returned.
        '''

        from utils import _search_scopus

        result_df, total_count = _search_scopus(self.apikey, query)
        if type(count) is not int or count > total_count:
            raise ValueError("%s is not a valid input for the number of entries to return." %number)

        if count < 25:
            # if less than 25, just one page of response is enough
            return result_df[:count]

        # if larger than, go to next few pages until enough
        index = 1
        while True:
            result_df = result_df.append(_search_scopus(self.apikey, query, index), ignore_index=True)
            if len(result_df) >= count:
                return result_df[:count]
            index += 1

    def search_author(self, query, count=10):
        '''
            Returns a list of author records in the form of pandas.DataFrame.

            Search for specific authors
            Details: http://api.elsevier.com/documentation/AUTHORSearchAPI.wadl
            Fields: http://api.elsevier.com/content/search/fields/author

            Parameters
            ----------------------------------------------------------------------
            query : str
                Query style (see above websites).
            count : int
                The number of records to be returned.
        '''

        from utils import _search_scopus

        result_df, total_count = _search_scopus(self.apikey, query, 2)
        if type(count) is not int or count > total_count:
            raise ValueError("%s is not a valid input for the number of entries to return." %number)

        if count < 25:
            # if less than 25, just one page of response is enough
            return result_df[:count]

        # if larger than, go to next few pages until enough
        index = 1
        while True:
            result_df = result_df.append(_search_scopus(self.apikey, query, 2, index), ignore_index=True)
            if len(result_df) >= count:
                return result_df[:count]
            index += 1

    def search_author_publication(self, author_id, show=True):
        #{{{ search author's publications using authid
        #TODO: Verbose mode

        '''
            Search author's publication by author id
            returns a list of dictionaries
        '''
        url = self._search_url_base + 'apikey={}&query=au-id({})&start=0&httpAccept=application/xml'.format(self.apikey, author_id)
        soup = bs(urlopen(url).read(), 'lxml')
        total = float(soup.find('opensearch:totalresults').text)
        print 'A toal number of ', int(total), ' records for author ', author_id
        starts = np.array([i*25 for i in range(int(np.ceil(total/25.)))])

        publication_list = []
        for start in starts:
            search_url = self._search_url_base + 'apikey={}&start={}&query=au-id({})&httpAccept=application/xml'.format(self.apikey, start, author_id)
            results = bs(urlopen(search_url).read(), 'lxml')
            entries = results.find_all('entry')
            for entry in entries:
                publication_list.append(_parse_xml(entry))

        if show:
            #pd.set_printoptions('display.expand_frame_repr', False)
            #print df['title'].to_string(max_rows=10, justify='left')
            df = pd.DataFrame(publication_list)
            titles = np.array(df['title'])
            for i in range(titles.size):
                t = trunc(titles[i])
                print '%d)' %i, t
        # }}}
        return publication_list
    
    def search_venue(self, venue_title, count=10, sort_by='relevency',\
            year_range=(1999, 2000), show=True):
        # {{{ search for papaers in a specific venue: journal, book, conference, or report
        #TODO: Verbose mode;
        #      Limited to "and" logic

        '''
            Search for papers in a specific venue
            return a dict of papers with keys being scopus ids and values as paper titles
        '''

        url = self._search_url_base +\
            'apikey={}&query=EXACTSRCTITLE({})&start=0&sort={}&date={}-{}&httpAccept=application/xml'\
            .format(self.apikey, quote(venue_title), sort_by, year_range[0], year_range[1])

        soup = bs(urlopen(url).read(), 'lxml')
        total = float(soup.find('opensearch:totalresults').text)

        paper_dict = {}

        starts = np.array([i*25 for i in range(int(np.ceil(total/25.)))])
        for start in starts:

            if len(paper_dict) >= count:
                break

            url = self._search_url_base +\
                'apikey={}&query=EXACTSRCTITLE({})&start={}&sort={}&date={}-{}&httpAccept=application/xml'\
                .format(self.apikey, quote(venue_title), start, sort_by, year_range[0], year_range[1])
            results = bs(urlopen(url).read(), 'lxml')
            entries = results.find_all('entry')
            for entry in entries:
                if len(paper_dict) >= count:
                    break
                sid = entry.find('dc:identifier').text.split(':')[-1]
                title = entry.find('dc:title').text
                paper_dict[sid] = title

        if show:
            print 'A total number of ', int(total), ' records for the venue %s from %d to %d.' \
                    %(venue_title, year_range[0], year_range[1])
            print 'Showing %d of them as requested ordered by %s.' %(count, sort_by)

            sid_list = paper_dict.keys()
            for i in range(len(sid_list)):
                print '%d)' %i, trunc(paper_dict[sid_list[i]])
        
        # return a dict of papers with keys being scopus ids and values as paper titles
        return paper_dict
        # }}}

    def retrieve_author(self, author_id, show=True, save_xml='./author_xmls'):
        #{{{ retrieve author info

        '''
            Search for specific authors
            Details: http://api.elsevier.com/documentation/AuthorRetrievalAPI.wadl

            returns a dictionary
        '''

        # parse query dictionary

        url = self._author_retrieve_url_base +\
            '{}?apikey={}&httpAccept=application/xml'.format(author_id, self.apikey)

        soup = bs(urlopen(url).read(), 'lxml')

        if save_xml is not None:
            if not os.path.exists(save_xml):
                os.makedirs(save_xml)
            with io.open('%s/%s.xml' %(save_xml, author_id), 'w', encoding='utf-8') as author_xml:
                author_xml.write(soup.prettify())

        author_info = _parse_author_retrieval(soup)

        # nothing find
        if not author_info:
            print 'No matched record found!'
            return None

        if show:
            print 'Name: %s' %(author_info['first-name'] + ' ' + author_info['last-name'])
            print 'Affiliation: %s (%s)' %(author_info['current-affiliation'][0]['name'],\
                    author_info['current-affiliation'][0]['address'])
        
        # }}}
        return author_info

    #def retrieve_abstract(self, scopus_id, force_ascii=False, show=True,\
    #        save_xml='./abstract_xml_files'):
    def retrieve_abstract(self, scopus_id, show=True,\
            save_xml='./abstract_xmls'):
        #{{{ search for abstracts
        #TODO: Verbose mode;

        '''
            returns a dictionary

            Update on 04/03/2016: add a save_xml flag
            Save to abstract_xml_files folder by default
        '''

        abstract_url = self._abstract_url_base + scopus_id + "?APIKEY={}&httpAccept=application/xml".format(self.apikey)

        # parse abstract xml
        try:
            abstract = bs(urlopen(abstract_url).read(), 'lxml')
            abstract_text = abstract.find('ce:para').text
            title = abstract.find('dc:title').text
        except:
            print 'Fail to find abstract!'
            return None

        if save_xml is not None:
            if not os.path.exists(save_xml):
                os.makedirs(save_xml)

            with io.open('%s/%s.xml'%(save_xml, scopus_id), 'w', encoding = 'utf-8') as xmlf:
                xmlf.write(abstract.prettify())
                
        '''
        # force encoding as utf-8
        if force_ascii:
            abstract_text = abstract_text.encode('ascii', 'ignore')
            title = title.encode('ascii', 'ignore')
        '''

        if show:
            print "\n####Retrieved info for publication %s (id: %s)####" % (title, scopus_id)
            print 'abstract: ', abstract_text
            print 
        #}}}
        return {'text':abstract_text, 'id':scopus_id,'title': title}

    def retrieve_citation(self, scopus_id, daterange=None, show=True, write2file=None):
        # {{{ retrieve annual citation counts
        '''
            daterange is a tuple
            write2file: file path
            return a list of citations over time
        '''

        # by default: recent three years
        if daterange is None:
            this_year = date.today().year
            daterange = (this_year-2, this_year)

        datestring = '%i-%i' %(daterange)
        
        if scopus_id is str or scopus_id is unicode:
            citation_url = "%sapikey=%s&scopus_id=%s&date=%s&httpAccept=application/xml" \
                    %(self._citation_overview_url_base, self.apikey, scopus_id, datestring)
        else:
            citation_url = "%sapikey=%s&scopus_id=%s&date=%s&httpAccept=application/xml" \
                    %(self._citation_overview_url_base, self.apikey, ",".join(scopus_id), datestring)

        soup = bs(urlopen(citation_url).read(), 'lxml')

        pub_citation_dict = _parse_citation(soup, daterange)

        if show:
            yearrange = range(daterange[0], daterange[1]+1)
            print 'Scopus ID\t StartYear\t Previous\t %s \t\t Later' %('\t\t '.join(map(str, yearrange)))
            for pub in pub_citation_dict:
                print '%s\t %i\t\t %i\t\t %s\t\t %i' %(pub, pub_citation_dict[pub]['year'],\
                    pub_citation_dict[pub]['previous_count'],\
                    '\t\t '.join(map(str, pub_citation_dict[pub]['annual_count'])),\
                    pub_citation_dict[pub]['later_count'])
        
        if write2file:
            f = io.open(write2file, 'w', encoding='utf-8')
            writer = csv.writer(f)
            yearrange = range(daterange[0], daterange[1]+1)
            writer.writerow(['Scopus ID', 'previous'] + yearrange + ['later'])
            for pub in pub_citation_dict:
                writer.writerow([pub, pub_citation_dict[pub]['previous_count']] + \
                    pub_citation_dict[pub]['annual_count'] + [pub_citation_dict[pub]['later_count']])

            f.close()

        # }}}
        return pub_citation_dict

