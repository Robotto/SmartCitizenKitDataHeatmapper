import scdata as sc
from scdata._config import config
import asyncio
import datetime

import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pickle

from project_secrets import * #Load api keys and stuff from file not in git.

def scrubData(df):
    rawCount=df.size

    df.index = pd.to_datetime(df.index, errors='dropna')
    # Ensure index is datetime

    # Drop rows without GPS coordinates/fix indication
    df = df.dropna(subset=['GPS_LAT', 'GPS_LONG', 'GPS_FIX'])

    df = df[df['GPS_FIX'] > 0] #Lower for more, but less locationally accurate data.

    print(f'Scrubbed {rawCount-df.size} rows. Sorted and dropped dataframe size: {df.size}')


    #print(df['GPS_FIX'])
    df = df.sort_index()
    return df


def loadSavedDataFrame():

    infile = open(f'SCK_{DEVICE_ID}.pk', 'rb')
    df = pickle.load(infile)
    infile.close()
    print("Loaded dataframe! Here's the header:")
    print(df.columns.values.tolist()) #Show column titles
    rawCount=df.size
    print(f'Raw dataframe size: {rawCount}')
    return df
    
def pullNewData(df):
    MINIMUM_DATE = None
    rawCount = 0
    if df is not None:
            MINIMUM_DATE = list(df.tail(1).index.strftime('%Y-%m-%d'))[0]
            rawCount = df.size
            print(f'Date for last entry in loaded data: {MINIMUM_DATE}') #TODO: GET A PROPER DATETIME OBJECT, TO COMPARE

    print(f"Fetching data for device #{DEVICE_ID} after: {MINIMUM_DATE}")

            # Set verbose level
    #config.log_level = 'DEBUG'

        # Device id needs to be as str
    device = sc.Device(blueprint='sc_air', params=sc.APIParams(id=DEVICE_ID))
    device.options.min_date = MINIMUM_DATE #Don't trim min_date
    device.options.max_date = None #Don't trim max_date
    #device.options.frequency = '1Min' # Use this to change the sample frequency for the request
    #print (device.json)

    # Load
    asyncio.run(device.load())

    freshdf = scrubData(device.data)

    df = pd.concat([df,freshdf])

    newSize = df.size
    delta = newSize - rawCount

    print(f"Got {delta} new rows of data! freshdf.size={freshdf.size}, df.size: before={rawCount}, after={newSize}, delta={delta}")
    
    return df


def saveDataFrame(df):
    outfile = open(f'SCK_{DEVICE_ID}.pk', 'wb')
    pickle.dump(df, outfile)
    outfile.close()
    
print(f"plotting data for device #{DEVICE_ID}...")

dataCount=0
try:
    df = loadSavedDataFrame()
    dataCount=df.size
except:
    print("Looks like there's no locally saved data... Starting from scratch.")
    df = None


df = pullNewData(df)
dataCountDelta = df.size-dataCount

if dataCountDelta>0:
    print("Looks like the dataframe got bigger. Pickling it now...")
    saveDataFrame(df)
    freshestTimestamp = list(df.tail(1).index.strftime('%Y-%m-%d %H:%M:%S'))[0]
    print(f'Freshest timestamp in pickle: {freshestTimestamp}')


# Identify sensor columns (exclude GPS)
sensor_columns = [c for c in df.columns if c not in ['GPS_LAT', 'GPS_LONG']]

# Compute mean center for initial map view
center_lat = 56.1558765#df['GPS_LAT'].mean()
center_lon = 10.1878436#df['GPS_LONG'].mean()

print(f"Hardcoded lat/lon mean: {center_lat},{center_lon}")

#center_lat = df['GPS_LAT'].mean()
#center_lon = df['GPS_LONG'].mean()

print(f"Calculated lat/lon mean: {center_lat},{center_lon}")

print("Click here: http://127.0.0.1:8050/")




# === Initialize Dash App ===
app = dash.Dash(__name__)
app.title = "SmartCitizen Map Dashboard"

app.layout = html.Div([
    html.H2("SmartCitizen Sensor Dashboard", style={"textAlign": "center"}),

    html.Div([
        html.Div([
            html.Label("Select sensors to display:"),
            dcc.Dropdown(
                id='sensor-dropdown',
                options=[{'label': col, 'value': col} for col in sensor_columns],
                value=['PMS5003_PM_25'],
                multi=True,
                clearable=False
            ),
        ], style={'width': '25%'}),

        html.Div([
            html.Label("Visualization mode:"),
            dcc.RadioItems(
                id='map-mode',
                options=[
                    {'label': 'Scatter Map', 'value': 'scatter'},
                    {'label': 'Heatmap', 'value': 'heatmap'}
                ],
                value='scatter',
                inline=True
            ),
            html.Label("Select time range:"),
            dcc.DatePickerRange(
                id='date-picker',
                start_date=(df.index.max().date()+datetime.timedelta(days=-1)),
                end_date=df.index.max().date(),
                display_format='YYYY-MM-DD',
            ),
        ], style={'width': '70%'}),
    ], style={'display': 'flex', 'justifyContent': 'space-between', 'padding': '10px'}),

    html.Div([
        dcc.Graph(id='map-graph', style={'flex': '1', 'height': '80vh', 'width': '100%'}, config={'scrollZoom': True})
    ], style={'flexGrow': 1})
], style={'display': 'flex', 'flexDirection': 'column', 'height': '100vh'})


# === Callback ===
@app.callback(
    Output('map-graph', 'figure'),
    Input('sensor-dropdown', 'value'),
    Input('map-mode', 'value'),
    Input('date-picker', 'start_date'),
    Input('date-picker', 'end_date')
)

def update_map(selected_sensors, map_mode, start_date, end_date):
    # Filter time range using index
    mask = (df.index >= start_date) & (df.index <= end_date)
    dff = df.loc[mask]

    if dff.empty:
        return go.Figure()

    fig = go.Figure()
    #fig.update_mapboxes(accesstoken=MAPBOX_API_KEY)

    # --- Add traces with offset colorbars ---
    for i, sensor in enumerate(selected_sensors):
        dff_sensor = dff.dropna(subset=[sensor])
        if dff_sensor.empty:
            continue

        # Colorbar offset (shift each bar a bit right)
        colorbar_x = 1.02 + 0.05 * i

        common_kwargs = dict(
            lat=dff_sensor['GPS_LAT'],
            lon=dff_sensor['GPS_LONG'],
           
            name=sensor,
        )

        if map_mode == 'scatter':
            fig.add_trace(go.Scattermap(
                **common_kwargs,
                mode='markers',
                marker=go.scattermap.Marker(
                    size=20,
                    color=dff_sensor[sensor]
                ),
                text=[
                    f"{sensor}: {v:.2f}<br>{i}"
                    for v, i in zip(dff_sensor[sensor], dff_sensor.index)
                ],
                hoverinfo='text',
            ))
        else:  # heatmap mode
            fig.add_trace(go.Densitymap(
                **common_kwargs,
                 colorscale='Viridis',
            showscale=True,
            colorbar=dict(title=sensor, x=colorbar_x),                 
                z=dff_sensor[sensor],
                radius=20
            ))

    # Determine map center dynamically
    map_center = {
        'lat': center_lat,
        'lon': center_lon
    }

    fig.update_layout(
        map=dict(
            #style="open-street-map",
            style="carto-darkmatter",
            #style="stamen-watercolor",
            #style="stamen-toner",
            zoom=15,
            center=map_center
        ),
        margin={"r": 100, "t": 40, "l": 0, "b": 0},
        title=f"{map_mode.capitalize()} view for {', '.join(selected_sensors)}"
    )

    return fig



if __name__ == '__main__':
    app.run(debug=True)



'''
def update_map(selected_sensors, map_mode, start_date, end_date):
    # Filter time range using index
    mask = (df.index >= start_date) & (df.index <= end_date)
    dff = df.loc[mask]

    if dff.empty:
        return go.Figure()

    fig = go.Figure()

    fig.update_mapboxes(accesstoken=MAPBOX_API_KEY)

    for sensor in selected_sensors:
        dff_sensor = dff.dropna(subset=[sensor])
        if dff_sensor.empty:
            continue

        if map_mode == 'scatter':
            fig.add_trace(go.Scattermapbox(
                lat=dff_sensor['GPS_LAT'],
                lon=dff_sensor['GPS_LONG'],
                mode='markers',
                marker=go.scattermapbox.Marker(
                    size=8,
                    color=dff_sensor[sensor],
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(title=sensor)
                ),
                text=[
                    f"{sensor}: {v:.2f}<br>{i}"
                    for v, i in zip(dff_sensor[sensor], dff_sensor.index)
                ],
                hoverinfo='text',
                name=sensor
            ))
        else:  # heatmap mode
            fig.add_trace(go.Densitymapbox(
                lat=dff_sensor['GPS_LAT'],
                lon=dff_sensor['GPS_LONG'],
                z=dff_sensor[sensor],
                radius=20,
                colorscale='Viridis',
                showscale=True,
                name=sensor,
                colorbar=dict(title=sensor)
            ))

    # Determine map center dynamically from filtered data
    map_center = {
        'lat': center_lat, #dff['GPS_LAT'].mean() if not dff['GPS_LAT'].empty else center_lat,
        'lon': center_lon #dff['GPS_LONG'].mean() if not dff['GPS_LONG'].empty else center_lon
    }

    fig.update_layout(
        mapbox=dict(
            #style="open-street-map",
            #style="carto-darkmatter",
            style="stamen-watercolor",
            #style="stamen-toner",
            zoom=15,
            center=map_center
        ),
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        title=f"{map_mode.capitalize()} view for {', '.join(selected_sensors)}"
    )

    return fig
'''
