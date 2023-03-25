#Importing all the relevant packages
import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import base64
import seaborn as sns

from sap import xssec
from cfenv import AppEnv
from flask import Flask, request, abort
from flask import render_template
from hdbcli import dbapi
from io import BytesIO

#Configuring Flask
app = Flask(__name__, template_folder='template')
env = AppEnv()
port = int(os.environ.get('PORT', 3000))
hana = env.get_service(label='hanatrial')
uaa_service = env.get_service(name='myuaa').credentials

@app.route('/')
def home():

#Authentication
    if 'authorization' not in request.headers:
        abort(403)
    access_token = request.headers.get('authorization')[7:]
    security_context = xssec.create_security_context(access_token, uaa_service)
    isAuthorized = security_context.check_scope('openid')
    if not isAuthorized:
        abort(403)

#Fetch HANA Credentials
    with open(os.path.join(os.getcwd(), 'env_cloud.json')) as f:
        hana_env_c = json.load(f)
        port_c = hana_env_c['port']
        user_c = hana_env_c['user']
        url_c = hana_env_c['url']
        pwd_c = hana_env_c['pwd']
    cc = dbapi.connect(url_c, port_c, user_c, pwd_c)

#Fetch Data from HANA Cloud Database
    cursor = cc.cursor()
    sql_select_Query = 'select "country", "year", "co2", "population", "gdp" from CO2_DATA'
    cursor.execute(sql_select_Query)

# Put it all to a Pandas data frame
    sql_data = pd.DataFrame(cursor.fetchall())
    headers = [i[0] for i in cursor.description]
    sql_data.columns = headers
    cursor.close()
    cc.close()

#Determining Correlation
    CO2_NUM = sql_data.copy()
    CO2_NUM.drop(['country', 'year'], axis='columns', inplace=True)
    CO2_NUM.dropna(inplace=True)
    CO2_NUM = CO2_NUM.astype('float64')
    corr = CO2_NUM.astype('float64').corr()

#Prepare Heatmap
    heat_map = BytesIO()
    sns.heatmap(data=corr, annot=True)
    plt.savefig(heat_map, format='png')
    heat_map.seek(0)  # rewind to beginning of file
    heatmapdata_png = base64.b64encode(heat_map.getvalue())

#Prepare Box Plot
    box_plot = BytesIO()
    plt.subplot(3, 2, 1)
    sns.boxplot(x=CO2_NUM['population'])
    plt.subplot(3, 2, 2)
    sns.boxplot(x=CO2_NUM['co2'])
    plt.subplot(3, 2, 5)
    sns.boxplot(x=CO2_NUM['gdp'])
    plt.savefig(box_plot, format='png')
    box_plot.seek(0)  # rewind to beginning of file
    boxplotdata_png = base64.b64encode(box_plot.getvalue())

# Plot ScatterPlot between Population and CO2
    scat1 = BytesIO()
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(sql_data['co2'], sql_data['population'])
    ax.set_xlabel('Population')
    ax.set_ylabel('Carbon Di Oxide')

    plt.savefig(scat1, format='png')
    scat1.seek(0)  # rewind to beginning of file
    scat1_png = base64.b64encode(scat1.getvalue())

# Plot ScatterPlot between Population and GDP
    scat2 = BytesIO()
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(sql_data['population'], sql_data['gdp'])
    ax.set_xlabel('Population')
    ax.set_ylabel('GDP')

    plt.savefig(scat2, format='png')
    scat2.seek(0)  # rewind to beginning of file
    scat2_png = base64.b64encode(scat2.getvalue())

#Return Rendered HTML
    return render_template("index.html",
                           heat_map=heatmapdata_png.decode('utf8'),
                           boxplot=boxplotdata_png.decode('utf8'),
                           scat1=scat1_png.decode('utf8'),
                           scat2=scat2_png.decode('utf8'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
