import time
import mido
from activelayer import ActiveLayer, ActiveLayerIdentifier
import threading


class RotaryEncoder:
    def __init__(self, encoder_index, outport: mido.ports.BaseOutput):
        self._encoder_index = encoder_index
        self._receive_data_cc = self._encoder_index
        self._receive_data_note = self._encoder_index - 1
        self._led_ring_value_cc = self._encoder_index + 8
        self._on_layer = ActiveLayerIdentifier.A
        self._simvar = None
        self._mobiflightsimvar = None
        self._event_up = None
        self._event_down = None
        self._alternate_event_up = None
        self._alternate_event_down = None
        self._alternate_active = False
        self._event_press = None
        self._event_press_short = None
        self._event_press_long = None
        self._time_of_note_on = time.time()
        self._current_led_ring_value = 0
        self._is_down = False
        self._time_long_press_thread = None
        self._long_press_timeout = 0

        if self._encoder_index > 8:
            self._receive_data_cc += 2
            self._receive_data_note += 16
            self._led_ring_value_cc -= 8
            self._on_layer = ActiveLayerIdentifier.B

        self._outport = outport
        ActiveLayer().subscribe_to_layer_change(self._on_layer_change)

    def set_led_ring_value(self, value: int, blink=False):
        if blink:
            value += 13
        self._current_led_ring_value = value

        if ActiveLayer().active_layer == self._on_layer:
            self._update_led_ring()

    def set_led_ring_on_off(self, on: bool, blink=False):
        if ActiveLayer().active_layer != self._on_layer:
            return
        value = 0
        if on:
            value = 27
            if blink:
                value = 28
        self._current_led_ring_value = value
        self._update_led_ring()

    def bind_led_to_simvar(self, simvar: str):
        self._simvar = simvar

    def bind_led_to_mobiflightsimvar(self, simvar: str):
        self._mobiflightsimvar = simvar

    def bind_to_event(self, event_up, event_down):
        self._event_up = event_up
        self._event_down = event_down

    def bind_to_alternate_event(self, event_up, event_down):
        self._alternate_event_up = event_up
        self._alternate_event_down = event_down

    def bind_press(self, event):
        self._event_press = event

    def bind_short_press(self, event):
        self._event_press_short = event

    def bind_long_press(self, event):
        self._event_press_long = event

    def reset_configuration(self):
        self._simvar = None
        self._mobiflightsimvar = None
        self._event_up = None
        self._event_down = None
        self._alternate_event_up = None
        self._alternate_event_down = None
        self._alternate_active = False
        self._event_press = None
        self._event_press_short = None
        self._event_press_long = None
        self._current_led_ring_value = 0

    @property
    def rotary_control_channel(self):
        return self._receive_data_cc

    @property
    def button_note(self):
        return self._receive_data_note

    @property
    def bound_simvar(self):
        return self._simvar

    @property
    def bound_mobiflightsimvar(self):
        return self._mobiflightsimvar


    def on_cc_data(self, value):
        print(f"on_cc_data: {self._encoder_index}: {value}")
        self._update_led_ring()
        self._update_active_layer()
        times = abs(64 - value)
        up_event = self._event_up
        down_event = self._event_down
        if times > 10:
            print("Either you're turning really fast, or encoder", self._encoder_index, "is not in relative 2 mode")
        if self._alternate_active:
            up_event = self._alternate_event_up
            down_event = self._alternate_event_down

        if value > 64 and up_event:
            for _ in range(times):
                up_event()
        elif down_event:
            for _ in range(times):
                down_event()

    def time_long_press(self):
        while True:
            diff_time = time.time() - self._time_of_note_on
            if self._is_down is False:
                print("short press")
                if self._event_press:
                    self._event_press()
                elif self._event_press_short:
                    self._event_press_short()
                return
            elif diff_time > self._long_press_timeout:
                print("long press")
                if self._event_press_long:
                    self._event_press_long()
                return
            time.sleep(0.05)

    def on_note_press(self):
        print(f"on_note_data ENC: {self._encoder_index}: press")
        self._update_active_layer()
        self._is_down = True
        self._time_of_note_on = time.time()
        self._time_long_press_thread = threading.Thread(target=self.time_long_press)
        self._time_long_press_thread.start()
    
    def on_note_release(self):
        print(f"on_note_data ENC: {self._encoder_index}: release")
        self._update_active_layer()
        self._is_down = False
        if self._time_long_press_thread is not None:
            self._time_long_press_thread.join()
    
    def set_long_press_timeout(self, timeout):
        self._long_press_timeout = timeout

    def on_alternate(self, enable: bool):
        self._alternate_active = enable

    def on_alternate_toggle(self, _):
        self._alternate_active = not self._alternate_active

    def on_simvar_data(self, data):
        if data == 1.0:
            self.set_led_ring_on_off(True)
        else:
            self.set_led_ring_on_off(False)

    def on_mobiflightsimvar_data(self, data):
        if data == 1.0:
            self.set_led_ring_on_off(True)
        else:
            self.set_led_ring_on_off(False)

    def _update_active_layer(self):
        ActiveLayer().active_layer = self._on_layer

    def _update_led_ring(self):
        msg = mido.Message('control_change', control=self._led_ring_value_cc, value=self._current_led_ring_value)
        self._outport.send(msg)

    def _on_layer_change(self, newlayer):
        if newlayer == self._on_layer:
            self._update_led_ring()
