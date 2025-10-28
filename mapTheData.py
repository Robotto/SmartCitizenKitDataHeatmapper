#import scdata as sc
#from scdata._config import config
#import asyncio

import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pickle



DEVICE_ID=15695
'''
#MINIMUM_DATE='2020-10-01'
MINIMUM_DATE=None
print(f"Getting data for device #{DEVICE_ID}...")

# Set verbose level
config.log_level = 'DEBUG'

# Device id needs to be as str
device = sc.Device(blueprint='sc_air',
                               params=sc.APIParams(id=DEVICE_ID))
device.options.min_date = MINIMUM_DATE #Don't trim min_date
device.options.max_date = None #Don't trim max_date
#device.options.frequency = '1Min' # Use this to change the sample frequency for the request
#print (device.json)

# Load
asyncio.run(device.load())
df=device.data
'''
print(f"plotting data for device #{DEVICE_ID}...")


infile = open(f'SCK_{DEVICE_ID}.pk','rb')
df = pickle.load(infile)

print("Loaded dataframe! Here's the header:")
print(df.columns.values.tolist()) #Show column titles

#print(df['GPS_FIX'])
rawCount=df.size

print(f'Raw dataframe size: {rawCount}')

# Ensure index is datetime
df.index = pd.to_datetime(df.index, errors='dropna')

# Drop rows without GPS coordinates/fix indication
df = df.dropna(subset=['GPS_LAT', 'GPS_LONG', 'GPS_FIX'])

df = df[df['GPS_FIX'] > 0] #Lower for more, but less locationally accurate data.

#print(df['GPS_FIX'])
df = df.sort_index()



#print(df)

print(f'Dropped {rawCount-df.size} rows. Sorted and dropped dataframe size: {df.size}')

# Identify sensor columns (exclude GPS)
sensor_columns = [c for c in df.columns if c not in ['GPS_LAT', 'GPS_LONG']]

# Compute mean center for initial map view
center_lat = 56.160795#df['GPS_LAT'].mean()
center_lon = 10.204074#df['GPS_LONG'].mean()

print(f"Hardcoded lat/lon mean: {center_lat},{center_lon}")

center_lat = df['GPS_LAT'].mean()
center_lon = df['GPS_LONG'].mean()

print(f"Calculated lat/lon mean: {center_lat},{center_lon}")

# === Initialize Dash App ===
app = dash.Dash(__name__)
app.title = "SmartCitizen Map Dashboard"

app.layout = html.Div([
    html.H2("SmartCitizen Sensor Dashboard", style={"textAlign": "center"}),

    html.Div([
        html.Label("Select sensors to display:"),
        dcc.Dropdown(
            id='sensor-dropdown',
            options=[{'label': col, 'value': col} for col in sensor_columns],
            value=['PMS5003_PM_25'],
            multi=True,
            clearable=False
        ),
    ], style={'width': '50%', 'display': 'inline-block', 'padding': '10px'}),

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
    ], style={'width': '40%', 'display': 'inline-block', 'padding': '10px'}),

    html.Div([
        html.Label("Select time range:"),
        dcc.DatePickerRange(
            id='date-picker',
            start_date=df.index.min().date(),
            end_date=df.index.max().date(),
            display_format='YYYY-MM-DD',
        ),
    ], style={'width': '40%', 'display': 'inline-block', 'padding': '10px'}),

    dcc.Graph(id='map-graph', style={'height': '90'},config={'scrollZoom':True}),
])

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
            style="carto-darkmatter",
            #style="stamen-watercolor",
            #style="stamen-toner",
            zoom=12,
            center=map_center
        ),
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        title=f"{map_mode.capitalize()} view for {', '.join(selected_sensors)}"
    )

    return fig


if __name__ == '__main__':
    app.run(debug=True)
