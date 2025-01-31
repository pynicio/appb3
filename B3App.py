# -*- coding: utf-8 -*-
# @Author: Your name
# @Date:   2025-01-27 22:35:33
# @Last Modified by:   Your name
# @Last Modified time: 2025-01-30 21:44:20
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State
import dash  # Import the dash module for callback_context
import numpy as np
import dash_bootstrap_components as dbc
import requests
from io import StringIO

# Load the data from the CSV file
csv_url = "https://storage.googleapis.com/b3datapy/b3.csv"
response = requests.get(csv_url)
if response.status_code == 200:
    df = pd.read_csv(StringIO(response.text), delimiter=";")
else:
    raise Exception(f"Failed to download CSV file from {csv_url}")

# Reformat 'HoraFechamento' from xxxxxxxx to a proper time format
def reformat_hora_fechamento(hora):
    hora_str = str(hora).zfill(8)  # Ensure 8 digits (pad with leading zeros if necessary)
    hours = int(hora_str[:2])
    minutes = int(hora_str[2:4])
    seconds = int(hora_str[4:6])
    milliseconds = int(hora_str[6:])
    
    if hours > 23 or minutes > 59 or seconds > 59:
        return None  # Invalid time, return None
    else:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:02d}"

df["HoraFechamento"] = df["HoraFechamento"].apply(reformat_hora_fechamento)
df = df.dropna(subset=["HoraFechamento"])
df["HoraFechamento"] = pd.to_datetime(df["HoraFechamento"], format="%H:%M:%S.%f")

# Reformat 'DataNegocio' from YYYY-MM-DD to DD-MM-YYYY
df["DataNegocio"] = pd.to_datetime(df["DataNegocio"]).dt.strftime("%d-%m-%Y")

# Fix the 'PrecoNegocio' column
df["PrecoNegocio"] = df["PrecoNegocio"].str.replace(",", ".").astype(float)

# Initialize the Dash app with Bootstrap
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # Required for Render deployment

# Calculate the mean price and count of transactions for each stock
mean_prices = df.groupby("CodigoInstrumento")["PrecoNegocio"].mean().round(2)
transaction_counts = df.groupby("CodigoInstrumento").size()

# Layout of the app
app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Stock Price Analysis", className="text-center"))),
    dbc.Row([
        dbc.Col([
            html.Label("Sort By:"),
            dcc.Dropdown(
                id="sort-dropdown",
                options=[
                    {"label": "CodigoInstrumento", "value": "CodigoInstrumento"},
                    {"label": "Mean Price", "value": "mean_price"},
                    {"label": "Transaction Count", "value": "transaction_count"},
                ],
                value="CodigoInstrumento",  # Default sorting method
                clearable=False,
            ),
            html.Label("Select CodigoInstrumento:"),
            dcc.Dropdown(
                id="codigo-dropdown",
                options=[],  # Will be populated dynamically
                value=None,  # No default value
                clearable=False,
            ),
            dbc.Button("Add Stock", id="add-stock-button", color="primary", className="mt-2"),
            dbc.Button("Clear All Stocks", id="clear-stocks-button", color="danger", className="mt-2"),
        ], width=4),
        dbc.Col([
            dcc.Checklist(
                id="stock-checklist",
                options=[],  # Will be populated dynamically
                value=[],  # No default value
                labelStyle={"display": "block"},  # Display checklist items vertically
            ),
        ], width=4),
    ]),
    dbc.Row(dbc.Col(dcc.Graph(id="price-plot"))),
])

# Callback to update the dropdown options based on sorting method
@app.callback(
    Output("codigo-dropdown", "options"),
    Input("sort-dropdown", "value")
)
def update_dropdown_options(sort_method):
    if sort_method == "CodigoInstrumento":
        sorted_codigos = sorted(mean_prices.index.tolist())
    elif sort_method == "mean_price":
        sorted_codigos = mean_prices.sort_values().index.tolist()
    elif sort_method == "transaction_count":
        sorted_codigos = transaction_counts.sort_values(ascending=False).index.tolist()
    else:
        sorted_codigos = mean_prices.index.tolist()

    options = [{"label": f"{codigo} (Mean: {mean_prices[codigo]}, Count: {transaction_counts[codigo]})", "value": codigo} for codigo in sorted_codigos]
    return options

# Callback to update the checklist and plot
@app.callback(
    [Output("stock-checklist", "options"),
     Output("stock-checklist", "value"),
     Output("price-plot", "figure")],
    [Input("add-stock-button", "n_clicks"),
     Input("clear-stocks-button", "n_clicks"),
     Input("stock-checklist", "value")],
    [State("codigo-dropdown", "value"),
     State("stock-checklist", "options")]
)
def update_plot(add_clicks, clear_clicks, selected_stocks, selected_codigo, checklist_options):
    fig = px.line(title="PrecoNegocio vs HoraFechamento")

    if add_clicks is None:
        add_clicks = 0
    if clear_clicks is None:
        clear_clicks = 0

    ctx = dash.callback_context
    if not ctx.triggered:
        button_id = None
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "clear-stocks-button":
        checklist_options = []
        selected_stocks = []
    elif button_id == "add-stock-button" and selected_codigo:
        if selected_codigo not in [option["value"] for option in checklist_options]:
            checklist_options.append({"label": f"{selected_codigo} (Mean: {mean_prices[selected_codigo]}, Count: {transaction_counts[selected_codigo]})", "value": selected_codigo})
            selected_stocks.append(selected_codigo)

    for stock in selected_stocks:
        filtered_df = df[df["CodigoInstrumento"] == stock]
        filtered_df = filtered_df.sort_values(by="HoraFechamento")
        fig.add_scatter(
            x=filtered_df["HoraFechamento"],
            y=filtered_df["PrecoNegocio"],
            mode="lines",
            name=f"{stock}",
        )

    fig.update_xaxes(
        title="HoraFechamento",
        type="date",
        tickformat="%H:%M:%S.%f",
    )
    fig.update_yaxes(title="PrecoNegocio")
    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
    )

    return checklist_options, selected_stocks, fig

# Run the app
if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)  # Updated for Render deployment
