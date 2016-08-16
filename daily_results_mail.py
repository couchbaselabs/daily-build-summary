__author__ = 'rsharma'


#!/usr/bin/env python
# _*_ coding:utf-8 _*_

import urllib2
#from jira import JIRA
from couchbase.bucket import Bucket
from couchbase.n1ql import N1QLQuery
from couchbase import Couchbase
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import sys
import time
import datetime
from datetime import timedelta
import calendar



'''
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
'''

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
    if len(build_no.split("-")[1]) == 3:
        build_no = (build_no.split("-")[0]) + "-0" + (build_no.split("-")[1])
    top_components = []
    detail_component = []
    conn = _sdk_connection()
    temp = 'SELECT component,totalCount,failCount,result from server WHERE `build` = ' + "'" + str(build_no) + "'"
    print temp
    q = N1QLQuery(temp)
    for row in conn.n1ql_query(q):
        #print row  # {'age': .., 'lname': ..., 'fname': ...}
        if row['component'] not in top_components:
            top_components.append(row['component'])
            detail_component.append({'component':row['component'],'totalCount':row['totalCount'],'failCount':row['failCount']})
        else:
            for details in detail_component:
                if (details['component'] == row['component']):
                    details['totalCount'] += row['totalCount']
                    details['failCount'] +=  row ['failCount']
    return detail_component,sorted(top_components)


def _construct_build_results_body(version_number,build_no):
    component_detail, top_component = query_build_results(version_number,build_no)
    defect_body = "<table border='1'style='float: left' cellpadding='5' cellspacing='5'>"
    defect_body = defect_body + \
            "<tr> " + \
            "<td colspan='3'> Build Number : {0}</td>".format(version_number+"-"+build_no) + \
            "</tr>" + \
            "<tr>" + \
            "<th> Component </th>" + \
            "<th> Total </th>"
    if (build_no.split("-")[0] == version_number):
            defect_body += "<th> Fail </th>" + \
            "<th> Fail % </th>" + \
            "</tr>"
    for i in range(0,len(top_component)):
        for j in range(0,len(component_detail)):
            if (component_detail[j]['component'] == top_component[i]):
                temp = component_detail[j]
                break;
        percentage = int((float(temp['failCount'])/float(temp['totalCount']))*100)
        defect_body += "<tr>" + \
        "<td>" + temp['component'] + "</td>" + \
        "<td>" + str(temp['totalCount']) + "</td>"
        if (build_no.split("-")[0] == version_number):
            defect_body += "<td>" + str(temp['failCount']) + "</td>"
            if int(percentage) >= 10:
                defect_body += "<td bgcolor='#FF33C7'>" + str(percentage) + "</td>" + "</tr>"
            else:
                defect_body += "<td>" + str(percentage) + "</td>" + "</tr>"
    defect_body += "</table>"
    return defect_body

def _get_change_list(start_build,end_build,version_number):
    print start_build.split("-")[0]
    if (start_build.split("-")[0]) == version_number:
        start_build = start_build.split("-")[1]
        end_build = end_build.split("-")[1]
        reformat = {}
        top_repo = []
        detail_repo = {}
        temp = "http://172.23.123.43:8282/changelog?ver={0}&from={1}&to={2}".format(version_number, start_build, end_build)
        print temp
        conn = urllib2.urlopen("http://172.23.123.43:8282/changelog?ver={0}&from={1}&to={2}".format(version_number, start_build, end_build))
        ret = json.loads(conn.read())

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
                if v['repo'] not in top_repo:
                    top_repo.append(v['repo'])
                    detail_repo[v['repo']] = v['message'][0:75] + "----" + v['committer']['name'] + "<br>"
                else:
                    temp = detail_repo[v['repo']]
                    detail_repo[v['repo']] = temp + v['message'][0:75] + "----" + v['committer']['name'] + "<br>"

        changes_body = "<table border='1'style='float: left' cellpadding='5' cellspacing='5'>"
        changes_body = changes_body + \
                      "<tr> " + \
                      "<td colspan='2'> Changes between Build Number : {0} - {1}</td>".format(version_number + "-" + start_build, version_number + "-" + end_build) + \
                      "</tr>" + \
                      "<tr>" + \
                      "<th> Projects </th>" + \
                      "<th> Commit </th>" + \
                      "</tr>"

        for i in range(0,len(top_repo)):
            changes_body += "<tr>" + \
                           "<td>" + top_repo[i] + "</td>" + \
                           "<td>" + detail_repo[top_repo[i]] + "</td>" + \
                            "</tr>"
        changes_body += "</table>"
        return changes_body
    return " "


def _construct_email_body(current_build,lastbuild,secondlastbuild,version_number):
    temp = "<h1> Today Daily Build - {0} </h1>".format(current_build)
    for i in range(0, len(lastbuild)):
        if (lastbuild[i].split("-")[0]) == version_number:
            temp += "<h1> Commit Between Build - {0} - {1} </h1> """.format(current_build,
                                                                            lastbuild[i]) + \
                   _get_change_list(lastbuild[i], current_build, version_number) + \
                   " <br> <br>"

        temp += "<div> <div style='float:left; width:100%'>  <h1> TestResults for Build - {0} and Build - {1} </h1>".format(lastbuild[i],secondlastbuild[i]) + \
                "<p>" +\
                   _construct_build_results_body(version_number, lastbuild[i]) + "" + \
                   _construct_build_results_body(version_number, secondlastbuild[i]) + \
                    "</div></p><br><br>"
    html = """\
        <html>
          <head></head>
          <body> """ + \
            temp + """\
         </body>
       </html>
       """
    print html
    return html

'''
def _construct_email_body(current_build,lastbuild,secondlastbuild,version_number):
    html = """\
        <html>
          <head></head>
          <body>  " +
            for i in range(0,len(lastbuild)):
                <h1> Today Daily Build - {0} </h1>  \
                <h1> Commit Between Build - {1} - {2}  </h1> """.format(current_build,
                                                                        lastbuild,
                                                                        current_build) + \
               _get_change_list(lastbuild, current_build, version_number) + \
               """<br> <br> <h1> Test Results for Build and Build </h1> <div>""" + \
               _construct_build_results_body(version_number, lastbuild) + "" + \
               _construct_build_results_body(version_number, secondlastbuild) + \
               """</div>
         </body>
       </html>
       """
    return html
'''


def _send_email(current_build,last_build,sec_last_build,version_number,password):
    from_email = 'ritamcouchbase@gmail.com'
    to_email = 'ritam@couchbase.com'
    email_body = ''
    email_recipients = ['ritam@couchbase.com','raju@couchbase.com']
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Daily Run Result'
    msg['From'] = from_email
    msg['To'] = ",".join(email_recipients)
    email_body += (_construct_email_body(current_build,last_build,sec_last_build,version_number))
    part1 = MIMEText(email_body, 'html')
    msg.attach(part1)
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.login('ritamcouchbase@gmail.com', password)
    server.sendmail(from_email, email_recipients, msg.as_string())
    server.quit()


def set_build_number(conn,version_no,build_number,build_date):
    if calendar.day_name[build_date.weekday()] == "Thursday":
        conn.upsert(str(build_date) + ":" + str(version_no), {'build_no': build_number,"run_type":"weekly"})
        conn.upsert("weekly_build" + "-" + version_no),{'build_no':build_number}
    else:
        conn.upsert(str(build_date)+ ":" + str(version_no), {'build_no': build_number, "run_type": "daily"})

def get_build_run_type(conn,build_date):
    build_run_type = conn.get(str(build_date)).value['run_type']
    return build_run_type

def get_all_details_from_doc(conn,build_date):
    build_run_type = conn.get(str(build_date)).value['run_type']
    build_no = conn.get(str(build_date)).value['build_no']
    return build_no, build_run_type


def check_docu_exists(conn,build_date):
    try:
        conn.get(str(build_date))
        return True
    except Exception as e:
        print "Error is {0}".format(e)
        return False


def main(argv):
    current_build = argv[0]
    last_released_build = argv[1]
    last_build_list = []
    build_before_last_list = []
    release_no = current_build.split("-")[0]
    conn = _sdk_connection(bucket='server', host_ip="172.23.121.131")
    today_date = datetime.date.today()

    set_build_number(conn,release_no,current_build,today_date)

    temp_last_build = "last_build" + "-" + release_no
    last_build = (conn.get(temp_last_build).value['build_no'])
    temp_second_last_before_build = "last_before_build" + "-" + release_no
    second_last_before_build = (conn.get(temp_second_last_before_build).value['build_no'])
    temp_last_weekly_build = "weekly_build" + "-" + release_no
    last_weekly_build = (conn.get(temp_last_weekly_build).value['build_no'])

    last_build_list.append(last_build)
    last_build_list.append(last_released_build)
    build_before_last_list.append(second_last_before_build)
    build_before_last_list.append(last_weekly_build)

    password = (conn.get('ritampass').value['password'])
    _send_email(current_build, last_build_list, build_before_last_list, release_no, password)
    conn.upsert(temp_last_build,{'build_no':current_build})
    conn.upsert(temp_second_last_before_build, {'build_no': last_build})


    '''
    #password = (conn.get('ritampass').value['password'])
    #password = 'r!bhu1008'
    #_send_email(current_build, lastbuild, secondlastbuild, version_no, password)
    #print today_date.weekday()
    #print calendar.day_name[today_date.weekday()]
    version_no = current_build[0:5]
    lastbuild = (conn.get('lastbuild').value['build_no']).split("-")[1]
    secondlastbuild = (conn.get('secondlastbuild').value['build_no']).split("-")[1]
    current_build = current_build.split("-")[1]
    time.sleep(30)
    password = (conn.get('ritampass').value['password'])
    password = "p@ssword@123"
    _send_email(current_build,lastbuild,secondlastbuild,version_no,password)
    #conn.upsert('lastbuild',{'build_no':version_no + "-" + current_build})
    #conn.upsert('secondlastbuild',{'build_no':version_no + "-" + lastbuild})
    '''


if __name__ == "__main__":
    main(sys.argv[1:])


