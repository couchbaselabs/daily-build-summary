__author__ = 'rsharma'


#!/usr/bin/env python
# _*_ coding:utf-8 _*_

import urllib2
from jira import JIRA
from couchbase.bucket import Bucket
from couchbase.n1ql import N1QLQuery
from couchbase import Couchbase
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import sys

def retrun_jira_24hrs():
    jira = JIRA({"server": "https://issues.couchbase.com"})
    issues = jira.search_issues("created>-1d AND project=MB")
    return_jira_list = []
    for tix in issues:
        bug = jira.issue(tix.key) #get the actual jira ticket with details
        #print bug.fields.summary
        #print bug.fields.components
        print type(bug.fields.components)
        print type(bug.fields.components[0])
        #print "Bug is is {0} - Component - {1} - Summary - {2}".format(tix,bug.fields.components, bug.fields.summary)
        return_jira_list.append("Bug No -  {0} - Component - {1} - Summary - {2}".format(tix,bug.fields.components, bug.fields.summary))
        #return return_jira_list
    return return_jira_list

def _sdk_connection(bucket='server',host_ip="172.23.121.131"):
    conn = Couchbase.connect (bucket=bucket, host=host_ip)
    return conn
    '''
    result = False
    connection_string = 'couchbase://'+ host_ip + '/' + bucket
    print connection_string
    try:
        cb = Bucket(connection_string)
        if cb is not None:
            result = True
            return result, cb
    except Exception, ex:
        print ex
        return result
    '''


def query_build_results(version_number=None,build_no=None):
    if build_no == None:
        return
    if len(build_no) == 3:
        build_no = '0' + build_no
    top_components = []
    detail_component = []
    conn = _sdk_connection()
    temp = 'SELECT component,totalCount,failCount,result from server WHERE `build` = ' + "'" + str(version_number+ "-" + build_no) + "'"
    print temp
    q = N1QLQuery(temp)
    for row in conn.n1ql_query(q):
        print row  # {'age': .., 'lname': ..., 'fname': ...}
        if row['component'] not in top_components:
            top_components.append(row['component'])
            detail_component.append({'component':row['component'],'totalCount':row['totalCount'],'failCount':row['failCount']})
        else:
            for details in detail_component:
                if (details['component'] == row['component']):
                    details['totalCount'] = details['totalCount'] + row['totalCount']
                    details['failCount'] = details['failCount'] + row ['failCount']
    return detail_component


def _construct_build_results_body(version_number,build_no):
    component_detail = query_build_results(version_number,build_no)
    defect_body = "<table border='1'style='float: left' cellpadding='5' cellspacing='5'>"
    defect_body = defect_body + \
            "<tr> " + \
            "<td colspan='3'> Build Number : {0}</td>".format(version_number+"-"+build_no) + \
            "</tr>" + \
            "<tr>" + \
            "<th> Component </th>" + \
            "<th> Total </th>" + \
            "<th> Fail </th>" + \
            "</tr>"
    for details in component_detail:
        defect_body = defect_body + "<tr>" + \
            "<td>" + details['component'] + "</td>" + \
            "<td>" + str(details['totalCount']) + "</td>" + \
            "<td>" + str(details['failCount']) + "</td>" + "</tr>"
    defect_body = defect_body + "</table>"
    return defect_body

def _get_change_list(start_build,end_build,version_no):
    conn = urllib2.urlopen("http://172.23.123.43:8282/changelog?ver={0}&from={1}&to={2}".format(version_no, start_build, end_build))
    ret = json.loads(conn.read())
    reformat = {}
    for val in ret['log']:
        if not reformat.has_key(val['repo']):
            reformat[val['repo']] = []
        reformat[val['repo']].append(val)
    keys = reformat.keys()
    keys.sort()
    ret1=''
    for k in keys:
        val = reformat[k]
        for v in val:
            ret1 += (v['message'])[0:75] + "----"
            ret1 += v['repo'] + "---"
            ret1 += v['fixes'] + "---"
            ret1 += v['committer']['name'] + "---" + "<br>"
    ret1 += "<br>"
    return ret1



def _send_email(current_build,lastbuild,secondlastbuild,version_number,password):
    from_email = 'ritamcouchbase@gmail.com'
    to_email = 'ritam@couchbase.com'
    email_recipients = ['ritam@couchbase.com']
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Test Subject'
    msg['From'] = from_email
    msg['To'] = ",".join(email_recipients)

    html = """\
    <html>
      <head></head>
      <body>  \
        <h1> Today Daily Build - {0} </h1>  \
        <h1> Commit Between Build - {1} - {2}  </h1> """.format(version_number+ "-"+ current_build,version_number + "-"+ lastbuild, version_number + "-"+ current_build) + \
        _get_change_list(lastbuild,current_build,version_number) + \
        """ <h1> Test Results for Build and Build </h1> <div>""" + \
        _construct_build_results_body(version_number,lastbuild) + \
        _construct_build_results_body(version_number,secondlastbuild) + \
        """</div>
      </body>
    </html>
    """

    part2 = MIMEText(html, 'html')
    msg.attach(part2)
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.login('ritamcouchbase@gmail.com', password)
    server.sendmail(from_email, email_recipients, msg.as_string())
    server.quit()


def main(argv):
    current_build = argv[0]
    print current_build
    conn = _sdk_connection(bucket='default',host_ip="172.23.107.7")
    version_no = current_build[0:5]
    lastbuild = (conn.get('lastbuild').value['build_no']).split("-")[1]
    secondlastbuild = (conn.get('secondlastbuild').value['build_no']).split("-")[1]
    current_build = current_build.split("-")[1]
    password = (conn.get('ritampass').value['password'])
    _send_email(current_build,lastbuild,secondlastbuild,version_no,password)
    conn.upsert('lastbuild',{'build_no':version_no + "-" + current_build})
    conn.upsert('secondlastbuild',{'build_no':version_no + "-" + lastbuild})


if __name__ == "__main__":
    main(sys.argv[1:])


