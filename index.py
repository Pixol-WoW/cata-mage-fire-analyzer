import panel as pn
pn.extension(design='material', theme='dark')
from urllib.parse import urlsplit
import asyncio
from utils.wcl.PixolWCLClient import WCLClient, UnauthenticatedQuery

from utils.analyzers.MageFire.PixolClassAnalyzerMageFire import PixolClassAnalyzerMageFire

import importlib
global HAS_PYSCRIPT
HAS_PYSCRIPT = importlib.util.find_spec('pyscript')
if HAS_PYSCRIPT:
    import js
    from pyweb import pydom
    from pyscript import window, document, display

class Menus:
    log_id = None
    client = None
    metadata = None
    current_task = None

    def __init__(self):
        self.passwordinput_clientid = self.PasswordInputClientID(self)
        self.passwordinput_clientsecret = self.PasswordInputClientSecret(self)
        self.button_saveclient = self.ButtonSaveClient(self)
        self.statictext_client = self.StaticText(self, text="")

        self.statictext_report = self.StaticText(self)
        self.textinput_report = self.TextInputReport(self)
        self.button_report = self.ButtonReport(self)

        self.select_analyzer = self.SelectAnalyzer(self)
        self.select_encounter = self.SelectEncounter(self)
        self.select_player = self.SelectPlayer(self)

        self.button_analyze = self.ButtonAnalyze(self)

        self._init_analyzers()

    class PasswordInputClientID:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.PasswordInput(name='WCL API Client ID', placeholder='WCL Client ID')
            self.load_saved_credentials()

        def load_saved_credentials(self):
            if HAS_PYSCRIPT:
                ls = window.localStorage
                self.obj.value = ls.getItem("WCLAnalyzerAPIClientID") or ""

    class PasswordInputClientSecret:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.PasswordInput(name='WCL API Client Secret', placeholder='WCL Client Secret')
            self.load_saved_credentials()

        def load_saved_credentials(self):
            if HAS_PYSCRIPT:
                ls = window.localStorage
                self.obj.value = ls.getItem("WCLAnalyzerAPIClientSecret") or ""

    class ButtonSaveClient:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.Button(icon='device-floppy', align='center', button_type='primary', margin=(5, 12, 0, -7))
            self.obj.on_click(self.handler)

        async def handler(self, event):
            if not event:
                return
            
            if HAS_PYSCRIPT:
                ls = window.localStorage

            client_id = self.parent.passwordinput_clientid.obj.value
            client_secret = self.parent.passwordinput_clientsecret.obj.value
            if client_id != "" and client_secret != "":
                if HAS_PYSCRIPT:
                    ls.setItem("WCLAnalyzerAPIClientID", client_id)
                    ls.setItem("WCLAnalyzerAPIClientSecret", client_secret)
                self.parent.statictext_client.SetText('Credentials saved!')
                self.parent.update_client()
            else:
                if client_id != "" or client_secret != "":
                    self.parent.statictext_client.SetText("Please complete both fields")
                else:
                    if HAS_PYSCRIPT:
                        ls.removeItem("WCLAnalyzerAPIClientID")
                        ls.removeItem("WCLAnalyzerAPIClientSecret")
                    self.parent.statictext_client.SetText("Credentials removed!")
                    self.parent.update_client()

    # -------------------------------------------------------------------------
    class StaticText:
        def __init__(self, parent, margin=(0,5,5,20), text=""):
            self.parent = parent
            self.obj = pn.widgets.StaticText(value='', margin=margin)
            self.SetText(text)

        def SetText(self, text):
            self.obj.value = text
            return

    # -------------------------------------------------------------------------
    class TextInputReport:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.TextInput(name='Enter WCL Report ID or URL', placeholder='https://classic.warcraftlogs.com/reports/aBcDeFg', width=500)
            pn.bind(self.handler, self.obj.param.value, watch=True)

            if HAS_PYSCRIPT:
                ls = window.localStorage
                self.obj.value = ls.getItem("WCLAnalyzerLogID") or ""

        def handler(self, input_url):
            if '.com' in input_url:
                log_id = urlsplit(input_url).path.split('/')[2]
            else:
                log_id = input_url

            if len(log_id) < 16 or len(log_id) > 18:
                self.parent.log_id = None
                self.parent.statictext_report.SetText('Invalid Log')
                return

            self.parent.log_id = log_id
            self.parent.statictext_report.SetText(f'Ready: {log_id}')
            
            return
        
    # -------------------------------------------------------------------------
    class ButtonReport:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.Button(icon='search', align='center', button_type='primary', margin=(5, 12, 0, -7))
            self.obj.on_click(self.handler)

        async def handler(self, event):
            if not event:
                return
            if not self.parent._is_task_done():
                return
            if self.parent.log_id:
                self.parent.statictext_report.SetText('Loading...')
                self.parent.current_task = asyncio.create_task(self.load_log(self.parent.log_id))
                await self.parent.current_task
        
        async def load_log(self, log_id):
            try:
                if not self.parent.client:
                    self.parent.update_client()
                self.parent.metadata = await self.parent.client._get_metadata(log_id)
                await asyncio.sleep(0.01)

                self.parent.select_player.obj.options = sorted(self.parent.metadata.df_mage_fire.name.to_list())
                self.parent.select_encounter.obj.options = self.parent.metadata.encounters.formattedName.to_list()[::-1]
                self.parent.statictext_report.SetText(f"Loaded: {log_id}<br>{await self.parent.client.get_api_rate()}")
                self.parent.select_analyzer.handler(None)
                if HAS_PYSCRIPT:
                    ls = window.localStorage
                    ls.setItem("WCLAnalyzerLogID", self.parent.log_id)
            except UnauthenticatedQuery as e:
                self.parent.statictext_report.SetText(f"UnauthenticatedQuery: Check WCL API Credentials under Settings")
            except Exception as e:
                self.parent.error = e
                self.parent.select_player.obj.options = []
                self.parent.select_encounter.obj.options = []
                self.parent.statictext_report.SetText(f"Error: {e}")
            await asyncio.sleep(1)

    # -------------------------------------------------------------------------
    class SelectAnalyzer:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.Select(name='Analyzer', options=[])
            pn.bind(self.handler, self.obj, watch=True)
        
        def handler(self, clicked):
            analyzer = self.parent.analyzers.get(self.parent.select_analyzer.obj.value)
            if analyzer:
                analyzer.on_menu_analyzer()

    # -------------------------------------------------------------------------
    class SelectEncounter:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.Select(name='Encounter', options=[])
            pn.bind(self.handler, self.obj, watch=True)
        
        def handler(self, clicked):
            analyzer = self.parent.analyzers.get(self.parent.select_analyzer.obj.value)
            if analyzer:
                analyzer.on_menu_encounter()

    # -------------------------------------------------------------------------
    class SelectPlayer:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.Select(name='Player', options=[], visible=False)
            pn.bind(self.handler, self.obj, watch=True)
        
        def handler(self, clicked):
            pass

    # -------------------------------------------------------------------------
    class ButtonAnalyze:
        def __init__(self, parent):
            self.parent = parent
            self.obj = pn.widgets.Button(icon='search', align='center', button_type='primary', margin=(5, 12, 0, -7))
            # pn.bind(self.handler, self.obj, watch=True)
            self.obj.on_click(self.handler)

        async def handler(self, event):
            if not event:
                return
            if not self.parent._is_task_done():
                return

            self.destroy_highcharts()
            analyzer = self.parent.analyzers.get(self.parent.select_analyzer.obj.value)
            if analyzer:
                self.parent.current_task = asyncio.create_task(analyzer.on_button_analyze())
                await self.parent.current_task

        def destroy_highcharts(self):
            pane_html_destroy_highcharts = pn.pane.HTML()
            pane_html_destroy_highcharts.object = "<script>destroyAllHighcharts()</script>"
            pane_html_destroy_highcharts.servable(target="destroyAllHighcharts")
            return
        

    # -------------------------------------------------------------------------
    class Analyzer:
        def __init__(self, parent):
            self.parent = parent

        def on_menu_analyzer(self):
            pass

        def on_menu_encounter(self):
            pass

        async def on_button_analyze(self):
            pass


    class AnalyzerMageFire(Analyzer):
        def on_menu_analyzer(self):
            self.parent.select_player.obj.visible = True
            if self.parent.metadata:
                self.parent.select_encounter.obj.options = self.parent.metadata.encounters.formattedName.to_list()[::-1]

        async def graph(self, log_id, fight_id, player_id):
            if HAS_PYSCRIPT:
                pydom['#panel2'][0].html = '<div id="pydomdiv"></div>'
            # await PixolWCLWarlock.generate_graph(self.parent.client, self.parent.metadata, log_id, fight_id, player_id, target_div="pydomdiv")
            obj_analyzer = PixolClassAnalyzerMageFire(self.parent.client, self.parent.metadata, player_id, fight_id)
            await obj_analyzer.fetch_events()
            obj_analyzer.generate_panel_to_div("pydomdiv")
            self.parent.statictext_report.SetText("Done")

        async def on_button_analyze(self):
            encounter = self.parent.select_encounter.obj.value
            if not encounter:
                self.parent.statictext_report.SetText("Please select an encounter")
                return
            player_name = self.parent.select_player.obj.value
            if not player_name:
                self.parent.statictext_report.SetText("Please select a player")
                return
            self.parent.statictext_report.SetText("Analyzing...")
            fight_id = self.parent.metadata.encounters[self.parent.metadata.encounters.formattedName==encounter].index.values[0]
            player_id = self.parent.metadata.df_mage_fire[self.parent.metadata.df_mage_fire.name == player_name].id.values[0]
            try:
                await self.graph(self.parent.log_id, fight_id, player_id)
            except Exception as e:
                self.parent.error = e
                self.parent.statictext_report.SetText(f"Error: {e}")
            await asyncio.sleep(1)

    def _init_analyzers(self):
        self.analyzers = {}
        self.analyzers['MageFire'] = self.AnalyzerMageFire(self)
        self.select_analyzer.obj.options = sorted(list(self.analyzers.keys()))
        self.select_analyzer.obj.value = self.select_analyzer.obj.options[0] 

    def _is_task_done(self):
        if self.current_task:
            if self.current_task.done():
                self.current_task = None
                return True
            return False
        else:
            return True
        
    def update_wcl_api_credentials(self):
        client_id = self.passwordinput_clientid.obj.value
        client_secret = self.passwordinput_clientsecret.obj.value
        self.client_id = client_id
        self.client_secret = client_secret

    def update_client(self):
        self.update_wcl_api_credentials()
        self.client = WCLClient(client_id=self.client_id, client_secret=self.client_secret)

    # -------------------------------------------------------------------------
    def get_menu_display(self):
        tab1 = pn.Column(
                    pn.Row(self.passwordinput_clientid.obj,
                        self.passwordinput_clientsecret.obj,
                        self.button_saveclient.obj,
                    ),
                    self.statictext_client.obj,
                    pn.widgets.StaticText(value="""
                        Enter your own WCL API Credentials or leave blank to use default.<br>
                        <a href="https://www.warcraftlogs.com/api/docs" target="_blank" style="color:#0072b5;">https://www.warcraftlogs.com/api/docs</a><br>
                        <a href="https://www.warcraftlogs.com/api/clients/" target="_blank" style="color:#0072b5;">https://www.warcraftlogs.com/api/clients/</a><br>
                    """)
            )
        tab2 = pn.Column(
                    pn.Row(self.textinput_report.obj,
                        self.button_report.obj,
                        self.select_analyzer.obj,
                        self.select_encounter.obj,
                        self.select_player.obj,
                        self.button_analyze.obj,
                    ),
                    self.statictext_report.obj,
            )
        custom_style = {
            'color': '#707073',
        }
        tabs = pn.Tabs(('Analyzer', tab2), ('Settings',tab1), styles=custom_style)
        return tabs


obj = Menus()
if HAS_PYSCRIPT:
    obj.get_menu_display().servable(target='panel')
else:
    display(obj.get_menu_display())

