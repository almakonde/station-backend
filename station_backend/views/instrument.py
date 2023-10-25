from flask import jsonify, request, make_response
from mjk_backend.restful import Restful

from mjk_vnc_backend.vnc import VNCView

from station_backend import sse


def _instrument_state_conv(state):
    return str(state).replace("InstrumentState.","")

def _ruia_state_conv(state):
    return str(state).replace("InstrumentRUIAState.","")


class InstrumentView(Restful):

    def __init__(self, app, psa, instrument):
        
        super().__init__(app, instrument.iid.lower())

        self.instrument = instrument
        self.vnc_url = None
        self.tc_url = None    

        if hasattr(self.instrument, 'ruia'):
            self.instrument.ruia.connect()
            if not ('vnc_url' in self.instrument.parameters.keys()):
                if 'vnc_host' in self.instrument.parameters['ruia'].keys():
                    vnc_view = VNCView(app, name=instrument.iid.lower()+'_vnc', path=self._path+'/vnc')
                    self.instrument.ruia.add_display(vnc_view)
                else:
                    if 'rest_host' in self.instrument.parameters['ruia'].keys():
                        self.rest_host = self.instrument.parameters['ruia']['rest_host']
                        self.rest_port = self.instrument.parameters['ruia']['rest_port']
                        self.vnc_url = "http://%s:%d/vnc" % (self.rest_host, self.rest_port)
                    else:
                        vnc_view = VNCView(app, name=instrument.iid.lower()+'_vnc', path=self._path+'/vnc')
                        self.instrument.ruia.add_display(vnc_view)


            self.instrument.ruia.bind('state', self._on_ruia_state_changed)

        self.instrument.bind('state', self._on_state_changed)

    def get(self, *args, **kwargs):
        data = {
            'iid': self.instrument.iid,
            'instrument_name': self.instrument.instrument_name,
            'vendor_name': self.instrument.vendor_name,
            'tc_url': self.tc_url,
            'vnc_url': self.instrument.parameters.get('vnc_url', self.vnc_url if (self.vnc_url is not None) else 'http://'+request.host+self._path+'/vnc'),
            'state': _instrument_state_conv(self.instrument.state),
            'error': str(self.instrument.error_string),
            'can_wake_up': hasattr(self.instrument, 'wake_up')
        }
        if hasattr(self.instrument, 'ruia'):
            data['ruia'] = {
                'state': _ruia_state_conv(self.instrument.ruia.state)
            }

        if hasattr(self.instrument, 'camera_plane'):
            data['camera_plane'] = {
                'initialized': self.instrument.camera_plane.initialized,
                'alpha': self.instrument.camera_plane.alpha,
                'beta_x': self.instrument.camera_plane.beta_x,
                'beta_y': self.instrument.camera_plane.beta_y,
                'gamma': self.instrument.camera_plane.gamma
            }
        if hasattr(self.instrument, 'parameters'):
            data['parameters'] = {
                
            }

        return jsonify(data)

    def put(self, *args, **kwargs):

        if request.is_json:
            command = request.json.get('command', None)
        else:
            command = request.args.get('command', None)

        if request.is_json:
            data = request.json.get('data', None)
        else:
            data = request.args.get('data', None)


        if command is not None:
            # data = request.json.get('data', None)
            if command == 'stop_ruia':
                if hasattr(self.instrument, 'ruia'):
                    self.instrument.ruia.set_as_finished()
                    return jsonify({})         
            elif command == 'wake_up':
                if hasattr(self.instrument, 'wake_up'):
                    self.instrument.wake_up()
                    return jsonify({})
                else:
                    return make_response('command wake_up not available', 500)
            else:
                return make_response('command not found', 500)
        else:
            return make_response('no command provided', 500)

    def _on_ruia_state_changed(self, *args, **kwargs):
        state = _ruia_state_conv(self.instrument.ruia.state)
        sse.push('/'.join([self.instrument.iid, 'ruia']), 'state', state)

    def _on_state_changed(self, *args, **kwargs):
        state = _instrument_state_conv(self.instrument.state)
        sse.push(self.instrument.iid, 'state', state)
    
