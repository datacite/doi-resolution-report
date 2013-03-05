#!/usr/bin/env python

import optparse, datetime, fnmatch, os, gzip, StringIO, csv, shutil, operator, re, calendar, locale
import markup, requests, cgi

FILE_PATTERN = 'access_log*.gz'
DOI_RESOLVER_URL = 'http://dx.doi.org/'
CONTENT_RESOLVER_URL = 'http://data.datacite.org/'
SEARCH_BY_PREFIX_URL = 'http://search.datacite.org/ui?q=*&fq=prefix:%s'
SEARCH_DATACENTRE_BY_PREFIX_URL = 'http://search.datacite.org/list/datacentres?fq=prefix:%s&facet.mincount=1'
TEST_PREFIX = '10.5072'

__version__ = '1.0'
__doc__ = '''Builds DOI resolution reports from CNRI logs.
The input_directory will be searched recursively for %s files.
The input_directory can be e.g /home/cnri. For each directory containing
files a report will be created. The name of the report will be based on the directory name.
The output_directory must exist. The files in the output directory will be overwritten.
''' % FILE_PATTERN

def timestamp():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d-%H%MZ")

def get_datacentres(prefix):
    symbols = requests.get(SEARCH_DATACENTRE_BY_PREFIX_URL % prefix).text
    for symbol in symbols.split('\n'):
        yield symbol.split(' ')[0]

def generate_html(name,
                  output_dir,
                  n_top,
                  prefixes,
                  prefix_successes,
                  prefix_failures,
                  prefix_unique_doi_successes,
                  prefix_unique_doi_failures,
                  prefix_top_dois_s,
                  prefix_top_dois_f):
    r = re.search('\d+', name)
    name = name[r.start():r.end()]
    m = name[-2:]
    y = name[:-2]
    name = calendar.month_name[int(m)] + ' ' + y
    page = markup.page()
    page.init(title="DOI resolution report " + name,
        script={'./static/jquery-1.7.2.min.js':"javascript", './static/jquery.tablesorter.min.js':"javascript"},
        css=('static/style.css'))
    page.h1("DOI resolution report " + name)
    page.br()
    page.table(id='rep', class_='tablesorter')
    page.thead()
    hard_space3 = '&nbsp;&nbsp;&nbsp;'
    page.th('#' + hard_space3)
    page.th('Prefix' + hard_space3)
    page.th('Total attempted' + hard_space3)
    page.th('Successful' + hard_space3)
    page.th('Failed' + hard_space3)
    page.th('Total unique DOIs' + hard_space3)
    page.th('Unique DOI: successes ' + hard_space3)
    page.th('Unique DOI: failures' + hard_space3)
    page.th('Top %s DOIs: successes ' % n_top + hard_space3)
    page.th('Top %s DOIs: failures ' % n_top + hard_space3)
    page.thead.close()
    page.tbody()
    ind = 1
    for p in prefixes:
        page.tr()
        page.td(ind)
        ind += 1
        page.td()
        page.a(p, href = SEARCH_BY_PREFIX_URL % p)
        for s in get_datacentres(p):
            page.p(str(s))
        page.td.close()
        page.td(prefix_successes[p] + prefix_failures[p])
        page.td(prefix_successes[p])
        page.td(prefix_failures[p])
        page.td(prefix_unique_doi_successes[p] + prefix_unique_doi_failures[p])
        page.td(prefix_unique_doi_successes[p])
        page.td(prefix_unique_doi_failures[p])
        page.td()
        page.ol()
        for d in prefix_top_dois_s[p]:
            page.li()
            page.a(cgi.escape(d[0]), href = DOI_RESOLVER_URL + d[0])
            page.a(' meta', href = CONTENT_RESOLVER_URL + d[0])
            page.i(' (' + str(d[1]) + ')')
            page.li.close()
        page.ol.close()
        page.td.close()
        page.td()
        page.ol()
        for d in prefix_top_dois_f[p]:
            page.li()
            page.a(cgi.escape(d[0]), href = DOI_RESOLVER_URL + d[0])
            page.a(' meta', href = CONTENT_RESOLVER_URL + d[0])
            page.i(' (' + str(d[1]) + ')')
            page.li.close()
        page.ol.close()
        page.td.close()
        page.tr.close()
    page.tfoot()
    page.tr()
    page.td('Total')
    page.td()
    locale.setlocale(locale.LC_ALL, 'en_US')
    page.td(locale.format("%d", sum(prefix_successes.values()) + sum(prefix_failures.values()), grouping=True))
    page.td(locale.format("%d", sum(prefix_successes.values()), grouping=True))
    page.td(locale.format("%d", sum(prefix_failures.values()), grouping=True))
    page.td(locale.format("%d", sum(prefix_unique_doi_successes.values()) + sum(prefix_unique_doi_failures.values()), grouping=True))
    page.td(locale.format("%d", sum(prefix_unique_doi_successes.values()), grouping=True))
    page.td(locale.format("%d", sum(prefix_unique_doi_failures.values()), grouping=True))
    page.td()
    page.td()
    page.tr.close()
    page.tfoot.close()
    page.tbody.close()
    page.table.close()
    page.script('''
    $(document).ready(function()
        {
            $("#rep").tablesorter();
        }
    );
    ''')
    file_name = 'resolutions_' + m + '_' + y + '.html'
    report_file_name = os.path.join(output_dir, file_name)
    with open(report_file_name, 'w') as f:
        f.write(str(page))
    return name, file_name, y+m

def filter_by_p(dictionary, p):
    return dict([(k,dictionary[k]) for k in dictionary if k.startswith(p)])

def create_report(root, files, output_dir, n_top):
    ss = {} # success doi => int count
    fs ={} # failure doi => int count
    for file in files:
        gz = gzip.open(os.path.join(root, file))
        content = gz.read()
        gz.close()
        lines = csv.reader(StringIO.StringIO(content), delimiter = ' ')
        for line in lines:
            success = line[4] == '1'
            doi = line[6]
            if doi.startswith('doi:'):
                doi = doi[4:]
            if success:
                ss[doi] = ss.get(doi, 0) + 1
            else:
                fs[doi] = fs.get(doi, 0) + 1
    dois = [s for s in ss] + [f for f in fs]
    prefixes = set([r.group(1) for r in [re.search("^(10\.\d+)/", doi) for doi in dois] if r])
    if TEST_PREFIX in prefixes: prefixes.remove(TEST_PREFIX)
    prefix_successes = dict([(p, sum([int(ss[x]) for x in ss if x.startswith(p)])) for p in prefixes])
    prefix_failures = dict([(p, sum([int(fs[x]) for x in fs if x.startswith(p)])) for p in prefixes])
    prefix_unique_doi_successes = dict([(p, len(set([x for x in ss if x.startswith(p)]))) for p in prefixes])
    prefix_unique_doi_failures = dict([(p, len(set([x for x in fs if x.startswith(p)]))) for p in prefixes])
    prefix_top_dois_s = dict([(p, sorted(filter_by_p(ss, p).iteritems(), key=operator.itemgetter(1), reverse=True)[:int(n_top)]) for p in prefixes])
    prefix_top_dois_f = dict([(p, sorted(filter_by_p(fs, p).iteritems(), key=operator.itemgetter(1), reverse=True)[:int(n_top)]) for p in prefixes])
    return generate_html(root.split('/')[-1],
        output_dir,
        n_top,
        prefixes,
        prefix_successes,
        prefix_failures,
        prefix_unique_doi_successes,
        prefix_unique_doi_failures,
        prefix_top_dois_s,
        prefix_top_dois_f)

def create_index_page(reports, output_dir):
    page = markup.page()
    page.init(title="DOI resolution reports ",
        script={'./static/jquery-1.7.2.min.js':"javascript", './static/jquery.tablesorter.min.js':"javascript"},
        css=('static/style.css'))
    page.h1("DOI resolution reports")
    page.br()
    for r in sorted(reports, key=lambda x:int(x[2])):
        page.p()
        page.a(r[0], href=r[1])
        page.p.close()

    static_target = os.path.join(output_dir, 'static')
    if not os.path.exists(static_target):
        shutil.copytree('static', static_target)
    index_file_name = os.path.join(output_dir, 'index.html')
    with open(index_file_name, 'w') as f:
        f.write(str(page))

def main():
    parser = optparse.OptionParser(description=__doc__,
        version=__version__,
        usage='%prog [OPTIONS] input_directory output_directory')
    #parser.add_option('-e', '--errors', default=False, action='store_true', help='log unsuccessful resolutions')
    parser.add_option('-n', '--n-top', default=10, action='store', metavar = 'N', help='include N top DOIs in reports, default %default')
    opts, args = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        exit(-1)
    files_by_dir = dict()
    matches = []
    for root, dir_names, file_names in os.walk(args[0]):
        for filename in fnmatch.filter(file_names, FILE_PATTERN):
            matches.append(os.path.join(root, filename))
    for ft in [os.path.split(p) for p in matches]:
        if not files_by_dir.has_key(ft[0]):
            files_by_dir[ft[0]] = []
        files_by_dir[ft[0]].append(ft[1])
    reports = []
    for d in files_by_dir:
        r = create_report(d, files_by_dir[d], args[1], opts.n_top)
        reports.append(r)
    create_index_page(reports, args[1])

if __name__ == '__main__':
    main()

