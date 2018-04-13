# Copyright Notice:
# Copyright 2018 Distributed Management Task Force, Inc. All rights reserved.
# License: BSD 3-Clause License. For full text see link: https://github.com/DMTF/Redfish-Service-Validator/blob/master/LICENSE.md

import time
from collections import Counter, OrderedDict
import traverseService as rst

EDM_NAMESPACE = "http://docs.oasis-open.org/odata/ns/edm"
EDMX_NAMESPACE = "http://docs.oasis-open.org/odata/ns/edmx"
EDM_TAGS = ['Action', 'Annotation', 'Collection', 'ComplexType', 'EntityContainer', 'EntityType', 'EnumType', 'Key',
            'Member', 'NavigationProperty', 'Parameter', 'Property', 'PropertyRef', 'PropertyValue', 'Record',
            'Schema', 'Singleton', 'Term', 'TypeDefinition']
EDMX_TAGS = ['DataServices', 'Edmx', 'Include', 'Reference']


def bad_edm_tags(tag):
    return tag.namespace == EDM_NAMESPACE and tag.name not in EDM_TAGS


def bad_edmx_tags(tag):
    return tag.namespace == EDMX_NAMESPACE and tag.name not in EDMX_TAGS


def other_ns_tags(tag):
    return tag.namespace != EDM_NAMESPACE and tag.namespace != EDMX_NAMESPACE


def reference_missing_uri_attr(tag):
    return tag.name == 'Reference' and tag.get('Uri') is None


def include_missing_namespace_attr(tag):
    return tag.name == 'Include' and tag.get('Namespace') is None


def format_tag_string(tag):
    tag_name = tag.name if tag.prefix is None else tag.prefix + ':' + tag.name
    tag_attr = ''
    for attr in tag.attrs:
        tag_attr += '{}="{}" '.format(attr, tag.attrs[attr])
    return (tag_name + ' ' + tag_attr).strip()


def tag_list_html(tags_dict):
    html_str = '<ul>'
    for tag in tags_dict:
        html_str += '<li>{} {}</li>' \
            .format(tag, '(' + str(tags_dict[tag]) + ' occurrences)' if tags_dict[tag] > 1 else '')
    html_str += '</ul>'
    return html_str


class Metadata(object):
    metadata_uri = '/redfish/v1/$metadata'
    schema_type = '$metadata'

    def __init__(self, logger):
        self.success_get = False
        self.soup = None
        self.service_refs = dict()
        self.elapsed_secs = 0
        self.metadata_namespaces = set()
        self.service_namespaces = set()
        self.bad_tags = dict()
        self.bad_tag_ns = dict()
        self.refs_missing_uri = dict()
        self.includes_missing_ns = dict()
        self.counter = OrderedCounter()
        self.logger = logger
        self.redfish_extensions_alias_ok = False

        start = time.time()
        success, soup, uri = rst.getSchemaDetails(Metadata.schema_type, Metadata.metadata_uri)
        self.elapsed_secs = time.time() - start
        if success:
            self.success_get = True
            self.soup = soup
            self.service_refs = rst.getReferenceDetails(soup, name=Metadata.schema_type)
            self.metadata_namespaces = {k for k in self.service_refs.keys()}
            logger.debug('Metadata: uri = {}'.format(uri))
            logger.debug('Metadata: metadata_namespaces: {} = {}'
                         .format(type(self.metadata_namespaces), self.metadata_namespaces))
            ref = self.service_refs.get('Redfish')
            if ref is not None and ref[0] == 'RedfishExtensions.v1_0_0':
                self.redfish_extensions_alias_ok = True
            logger.debug('Metadata: redfish_extensions_alias_ok = {}'.format(self.redfish_extensions_alias_ok))
            self.check_tags(soup)
            logger.debug('Metadata: bad_tags = {}'.format(self.bad_tags))
            logger.debug('Metadata: bad_tag_ns = {}'.format(self.bad_tag_ns))
            logger.debug('Metadata: refs_missing_uri = {}'.format(self.refs_missing_uri))
            logger.debug('Metadata: includes_missing_ns = {}'.format(self.includes_missing_ns))
        else:
            logger.warning('Metadata: getSchemaDetails() did not return success')

    def get_soup(self):
        return self.soup

    def get_service_refs(self):
        return self.service_refs

    def get_metadata_namespaces(self):
        return self.metadata_namespaces

    def get_service_namespaces(self):
        return self.service_namespaces

    def add_service_namespace(self, namespace):
        self.service_namespaces.add(namespace)

    def get_missing_namespaces(self):
        return self.service_namespaces - self.metadata_namespaces

    def get_schema_uri(self, namespace):
        ref = self.service_refs.get(namespace)
        if ref is not None:
            return ref[1]
        else:
            return None

    def check_tags(self, soup):
        try:
            for tag in soup.find_all(bad_edm_tags):
                tag_str = format_tag_string(tag)
                self.bad_tags[tag_str] = self.bad_tags.get(tag_str, 0) + 1
            for tag in soup.find_all(bad_edmx_tags):
                tag_str = format_tag_string(tag)
                self.bad_tags[tag_str] = self.bad_tags.get(tag_str, 0) + 1
            for tag in soup.find_all(reference_missing_uri_attr):
                tag_str = format_tag_string(tag)
                self.refs_missing_uri[tag_str] = self.refs_missing_uri.get(tag_str, 0) + 1
            for tag in soup.find_all(include_missing_namespace_attr):
                tag_str = format_tag_string(tag)
                self.includes_missing_ns[tag_str] = self.includes_missing_ns.get(tag_str, 0) + 1
            for tag in soup.find_all(other_ns_tags):
                tag_str = tag.name if tag.prefix is None else tag.prefix + ':' + tag.name
                tag_ns = 'xmlns{}="{}"'.format(':' + tag.prefix if tag.prefix is not None else '', tag.namespace)
                tag_str = tag_str + ' ' + tag_ns
                self.bad_tag_ns[tag_str] = self.bad_tag_ns.get(tag_str, 0) + 1
        except Exception as e:
            self.logger.warning('Metadata: Problem parsing $metadata document: {}'.format(e))

    def get_counter(self):
        counter = OrderedCounter()
        # informational counters
        counter['metadataNamespaces'] = len(self.metadata_namespaces)
        counter['serviceNamespaces'] = len(self.service_namespaces)
        # error counters
        counter['missingRedfishAlias'] = 0 if self.redfish_extensions_alias_ok else 1
        counter['missingNamespaces'] = len(self.get_missing_namespaces())
        counter['badTags'] = len(self.bad_tags)
        counter['missingUriAttr'] = len(self.refs_missing_uri)
        counter['missingNamespaceAttr'] = len(self.includes_missing_ns)
        counter['badTagNamespaces'] = len(self.bad_tag_ns)
        self.counter = counter
        return self.counter

    def to_html(self):
        time_str = 'response time {0:.6f}s'.format(self.elapsed_secs)
        section_title = '{} ({})'.format(Metadata.metadata_uri, time_str)

        counter = self.get_counter()

        html_str = ''
        html_str += '<tr><th class="titlerow bluebg"><b>{}</b></th></tr>'\
            .format(section_title)
        html_str += '<tr><td class="titlerow"><table class="titletable"><tr>'
        html_str += '<td class="title" style="width:40%"><div>{}</div>\
                        <div class="button warn" onClick="document.getElementById(\'resMetadata\').classList.toggle(\'resultsShow\');">Show results</div>\
                        </td>'.format(section_title)
        html_str += '<td class="titlesub log" style="width:30%"><div><b>Schema File:</b> {}</div><div><b>Resource Type:</b> {}</div></td>'\
            .format(Metadata.metadata_uri, Metadata.schema_type)
        html_str += '<td style="width:10%"' + \
            ('class="pass"> GET Success' if self.success_get else 'class="fail"> GET Failure') + '</td>'
        html_str += '<td style="width:10%">'

        errors_found = False
        for count_type in counter.keys():
            style = 'class=log'
            if 'bad' in count_type or 'missing' in count_type:
                if counter[count_type] > 0:
                    errors_found = True
                    style = 'class="fail log"'
            html_str += '<div {style}>{p}: {q}</div>'.format(
                    p=count_type, q=counter.get(count_type, 0), style=style)

        html_str += '</td></tr>'
        html_str += '</table></td></tr>'
        html_str += '<tr><td class="results" id=\'resMetadata\'><table><tr><th>$metadata validation results</th></tr>'

        if self.success_get and not errors_found:
            html_str += '<tr><td class="pass log">Validation successful</td></tr>'
        elif not self.success_get:
            html_str += '<tr><td class="fail log">ERROR - Unable to retrieve $metadata resource at {}</td></tr>'\
                .format(Metadata.metadata_uri)
        else:
            if not self.redfish_extensions_alias_ok:
                html_str += '<tr><td class="fail log">ERROR - $metadata does not include the required "RedfishExtensions.v1_0_0" namespace with an alias of "Redfish"</td></tr>'
            if len(self.get_missing_namespaces()) > 0:
                html_str += '<tr><td class="fail log">ERROR - The following namespaces are referenced by the service, but are not included in $metadata:<ul>'
                for ns in self.get_missing_namespaces():
                    html_str += '<li>{}</li>'.format(ns)
                html_str += '</ul></td></tr>'
            if len(self.bad_tags) > 0:
                html_str += '<tr><td class="fail log">ERROR - The following tag names in $metadata are unrecognized (check spelling or case):'
                html_str += tag_list_html(self.bad_tags)
                html_str += '</td></tr>'
            if len(self.refs_missing_uri) > 0:
                html_str += '<tr><td class="fail log">ERROR - The following Reference tags in $metadata are missing the expected Uri attribute (check spelling or case):'
                html_str += tag_list_html(self.refs_missing_uri)
                html_str += '</td></tr>'
            if len(self.includes_missing_ns) > 0:
                html_str += '<tr><td class="fail log">ERROR - The following Include tags in $metadata are missing the expected Namespace attribute (check spelling or case):'
                html_str += tag_list_html(self.includes_missing_ns)
                html_str += '</td></tr>'
            if len(self.bad_tag_ns) > 0:
                html_str += '<tr><td class="fail log">ERROR - The following tags in $metadata have an unexpected namespace:'
                html_str += tag_list_html(self.bad_tag_ns)
                html_str += '</td></tr>'
        html_str += '</table>'

        return html_str


class OrderedCounter(Counter, OrderedDict):
    """Counter that remembers the order elements are first encountered"""

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, OrderedDict(self))

    def __reduce__(self):
        return self.__class__, (OrderedDict(self),)