#!/usr/bin/python
# -*- coding: utf-8 -*-

# Created on: 8 Oct 2014

__author__ = 'karas84'

from gi import require_version
require_version("Gtk", "3.0")
require_version('AppIndicator3', '0.1')
from gi.repository import Gio, Gtk, GObject
from gi.repository import AppIndicator3 as AppIndicator

import sys
import os
import threading
import time
import subprocess
import tempfile
import PIL.Image
import re
import sys

import Xlib
import Xlib.ext

from Xlib import X, display, xobject
from Xlib.error import BadWindow, CatchError

VIBER_STATUS_NORMAL = "viber-indicator"
VIBER_STATUS_NOTIFICATION = "viber-notification"


def printf(str_format, *args):
    sys.stdout.write(str_format % args)
    sys.stdout.flush()


class FilteredStdOut(object):
    """class description"""

    def __init__(self):
        self.wrapped_stdout = sys.stdout
        self.skip_next = False


    def __getattribute__(self,name):
        if name == "wrapped_stdout" or name == "write" or name == "filter" or name == "skip_next":
            return object.__getattribute__(self, name)
        else:
            return self.wrapped_stdout.__class__.__getattribute__(self.wrapped_stdout, name)


    def write(self, s):
        if self.skip_next:
            self.skip_next = False
        elif self.filter(s):
            self.wrapped_stdout.write(s)


    def filter(self, s):
        if "<class 'Xlib.protocol.request.QueryExtension'>" in s:
            self.skip_next = True

            return False
        else:
            return True


sys.stdout = FilteredStdOut()



class XTools(object):
    """class description"""

    INSTANCE = None

    def __init__(self):
        if self.INSTANCE is not None:
            raise ValueError("An instantiation already exists!")

        self.display = display.Display()
        self.root = self.display.screen().root


    @classmethod
    def Instance(cls):
        if cls.INSTANCE is None:
             cls.INSTANCE = XTools()

        return cls.INSTANCE


    def get_root(self):
        return self.root


    def get_display(self):
        return self.display


    def create_window_from_id(self, window_id):
        return self.display.create_resource_object('window', window_id)


    def get_client_list(self):
        return self.root.get_full_property(self.display.intern_atom('_NET_CLIENT_LIST'), Xlib.X.AnyPropertyType).value


    def get_mouse_location(self):
        data = self.root.query_pointer()._data
        return data["root_x"], data["root_y"]


    @staticmethod
    def translate_coordinates(window, src_window, src_x, src_y):
        data = window.translate_coords(src_window, src_x, src_y)._data
        return data['x'], data['y']


    def get_input_state(self):
        data = self.root.query_pointer()._data
        return data['mask']


    def mousebutton(self, window, button=1, is_press=True):
        XButtons = {
            1: X.Button1,
            2: X.Button2,
            3: X.Button3,
            4: X.Button4,
            5: X.Button5
        }

        XButtonMasks = {
            1: X.Button1MotionMask,
            2: X.Button2MotionMask,
            3: X.Button3MotionMask,
            4: X.Button4MotionMask,
            5: X.Button5MotionMask
        }

        XEvent = {
            True: Xlib.protocol.event.ButtonPress,
            False: Xlib.protocol.event.ButtonRelease
        }

        root_x, root_y = self.get_mouse_location()
        state = self.get_input_state()
        x, y = self.translate_coordinates(window, self.root, root_x, root_y)

        if not is_press:
            state |= XButtonMasks[button]


        XEventFunction = XEvent[is_press]
        mouse_event = XEventFunction(detail=XButtons[button],
                                     root=self.root, root_x=root_x, root_y=root_y,
                                     window=window, event_x=x, event_y=y,
                                     same_screen=1, state=state,
                                     time=X.CurrentTime, child=0)

        window.send_event(event=mouse_event, event_mask=X.ButtonPressMask, propagate=1)


    def mouse_up(self, window, button):
        self.mousebutton(window, button, is_press=False)


    def mouse_down(self, window, button):
        self.mousebutton(window, button, is_press=True)


    def get_window_by_class_name(self, class_name):
        XTools.Instance().get_display().sync()
        window = None

        for win in self.root.query_tree().children:
            try:
                window_wm_class = win.get_wm_class()
                if window_wm_class is not None:
                    if class_name in window_wm_class[0] or class_name in window_wm_class[1]:
                        window = self.display.create_resource_object('window', win.id)
                        break
            except BadWindow:
                printf("Error getting window's WM_CLASS of window 0x%08x\n", win.id)
                pass

        return window


    def get_client_by_class_name(self, class_name):
        XTools.Instance().get_display().sync()
        window = None

        for win_id in self.get_client_list():
            try:
                win = self.create_window_from_id(win_id)
                wclass = win.get_wm_class()
                if wclass is not None and (class_name in wclass[0] or class_name in wclass[1]):
                    window = win
                    break
            except BadWindow:
                printf("Error getting client's WM_CLASS of window 0x%08x\n", win_id)
                pass

        return window


class XWindow(object):
    """class description"""

    class WindowIsNone(Exception):
        """class description"""

        def __init__(self):
            super(XWindow.WindowIsNone, self).__init__("Window is None")


    def __init__(self, window):
        if window is None:
            raise XWindow.WindowIsNone

        self.XTools = XTools.Instance()
        self.window = window


    def click(self, button=1):
        self.XTools.mouse_down(self.window, button)
        self.XTools.mouse_up(self.window, button)


    def double_click(self, button=1):
        self.click(button)
        self.click(button)


    def close(self):
        _NET_CLOSE_WINDOW = self.XTools.get_display().intern_atom("_NET_CLOSE_WINDOW")

        close_message = Xlib.protocol.event.ClientMessage(window=self.window, client_type=_NET_CLOSE_WINDOW, data=(32,[0,0,0,0,0]))
        mask = (X.SubstructureRedirectMask | X.SubstructureNotifyMask)

        self.XTools.Instance().get_root().send_event(close_message, event_mask=mask)
        self.XTools.get_display().flush()


    def hide(self):
        Xlib.protocol.request.UnmapWindow(display=self.XTools.get_display().display, window=self.window.id)
        self.XTools.get_display().sync()


    def show(self):
        Xlib.protocol.request.MapWindow(display=self.XTools.get_display().display, window=self.window.id)
        self.XTools.get_display().sync()


    def move(self, x, y):
        win = xobject.drawable.Window(self.XTools.get_display().display, self.window.id)
        w_geom = self.window.get_geometry()._data
        win.configure(x=x, y=y, width=w_geom['width'], height=w_geom['height'])
        win.change_attributes(win_gravity=X.NorthWestGravity, bit_gravity=X.StaticGravity)
        self.XTools.get_display().sync()


    def read_image(self, width, height, save_to=None):
        pixmp = self.window.get_image(0, 0, width, height, Xlib.X.ZPixmap, 0xFFFFFFFF)
        rgbim = PIL.Image.frombytes("RGB", (width, height), pixmp.data, "raw", "BGRX")

        if save_to is not None:
            rgbim.save(save_to)

        return rgbim


    def next_event(self, instance=None, atom=None):
        ev = None
        while ev is None:
            ev = self.window.display.next_event()

            if atom is not None:
                ev = ev if hasattr(ev, 'atom') and ev.atom == atom else None

            if instance is not None:
                ev = ev if isinstance(ev, instance) else None

        return ev


class ViberIconPoller(threading.Thread):
    """class description"""

    def __init__(self, xviber_window):
        super(ViberIconPoller, self).__init__()
        self.viber_window = xviber_window
        self.setDaemon(True)


    def run(self):
        self.poll_viber_icon()


    def poll_viber_icon(self):

        notified = False
        while True:
            try:
                time.sleep(1)
                n = self.is_notified()
            except:
                n = False

            if n and not notified:
                notified = True
                indicator.set_icon(VIBER_STATUS_NOTIFICATION)
                indicator.set_status(AppIndicator.IndicatorStatus.ATTENTION)
            elif not n and notified:
                notified = False
                indicator.set_icon(VIBER_STATUS_NORMAL)
                indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)


    def is_notified(self):
        viber_img = self.viber_window.read_image(22, 22)
        r, g, b = viber_img.getpixel((17, 4))

        if r >= 200 and g <= 50 and b <= 50:
            return True

        return False


class ViberChatWindow(XWindow):
    """class description"""

    @staticmethod
    def get_viber_chat():
        window = None

        windowIDs = XTools.Instance().get_client_list()
        for windowID in windowIDs:
            window = XTools.Instance().create_window_from_id(windowID)
            wclass = window.get_wm_class()

            if wclass is None:
                continue

            if "Viber" in wclass[0] or "Viber" in wclass[1]:
                break

        return window


    def __init__(self):
        super(ViberChatWindow, self).__init__(ViberChatWindow.get_viber_chat())


class NoViberWindowFound(Exception):
        """class description"""

        def __init__(self):
            super(NoViberWindowFound, self).__init__("No Viber Window Found")


class CompizNotFound(Exception):

    def __init__(self):
        super(CompizNotFound, self).__init__()


class ViberAlreadyRunning(Exception):

    def __init__(self):
        super(ViberAlreadyRunning, self).__init__()


class ViberWindow(XWindow):
    """class description"""

    @staticmethod
    def external_find_viber():
        r = subprocess.Popen(["xwininfo", "-root", "-children"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ou, er = map(lambda s: s.strip(), r.communicate())

        if len(ou) > 0 and len(er) == 0:
            ou = [i for i in ou.split('\n') if "ViberPC" in i and "+0+0" in i]

            if len(ou) == 0:
                return None

            try:
                viber_window_id = int(re.match(r"^ *(0x[^ ]+) .*$", ou[0]).groups()[0], base=16)
            except:
                return None

            return XTools.Instance().create_window_from_id(viber_window_id)
        else:
            return None


    def find_viber(self):
        while self.viber_window is None:
            if self.w_compiz.next_event():
                self.viber_window = XTools.Instance().get_window_by_class_name('ViberPC')


    @staticmethod
    def get_viber_window():
        children = XTools.Instance().get_root().query_tree().children

        found_viber_window = None
        for window in children:
            try:
                w_class = window.get_wm_class()
                if w_class is not None:
                    if "viber" in w_class[0].lower() or "viber" in w_class[1].lower():
                        geom = window.get_geometry()._data
                        if geom['x'] == 0 and geom['y'] == 0 and geom['width'] <= 64 and geom['height'] <= 64:
                            found_viber_window = window
            except:
                pass

        return found_viber_window


    def poll_viber_window(self, external=False):
        if external:
            printf(" (EXTERNAL)\n")
            finder_fn = ViberWindow.external_find_viber
        else:
            printf(" (INTERNAL)\n")
            finder_fn = ViberWindow.get_viber_window

        found_viber_window = finder_fn()

        poll_second_count = 10
        while poll_second_count > 0:
            if found_viber_window is not None:
                break

            time.sleep(1)
            poll_second_count -= 1

            found_viber_window = finder_fn()

        self.viber_window = found_viber_window


    def __init__(self, close_chat=False, use_old=False, use_external=False):
        self.viber_window = None
        self.viber_launcher = ViberLauncher()

        try:
            if use_old:
                raise CompizNotFound()

            try:
                self.w_compiz = XWindow(XTools.Instance().get_window_by_class_name('compiz'))
            except XWindow.WindowIsNone:
                raise CompizNotFound()

            printf("Using NEW detection method\n")

            XTools.Instance().get_root().change_attributes(event_mask=X.SubstructureNotifyMask)
            self.w_compiz.window.change_attributes(event_mask=X.SubstructureNotifyMask)

            self.thread = threading.Thread(target=self.find_viber)
        except CompizNotFound:
            printf("Using OLD detection method")

            self.thread = threading.Thread(target=self.poll_viber_window, kwargs={"external": use_old and use_external})

        self.thread.setDaemon(True)
        self.thread.start()

        self.viber_launcher.start()

        self.thread.join()

        super(ViberWindow, self).__init__(self.viber_window)

        if self.window is None:
            raise NoViberWindowFound

        self.move(-128, -128)

        printf("Viber Found")

        if close_chat:
            self.chat_window = ViberChatWindow()
            self.chat_window.close()


    def open(self, widget, data=None):
        self.double_click(button=1)


    def quit(self, widget, data=None):
        os.system('pkill -9 Viber')


class ProcessFinder(object):
    """class description"""

    def __init__(self, process_path):
        self.process_path = process_path.strip().replace('\t', ' ')
        self.re = re.compile(r".* " + re.escape(self.process_path) + r"$")

        self._found = None


    def _find_process(self):
        self._found = False

        ret = subprocess.Popen(['ps', '-aux'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_stream, err_stream = ret.communicate()

        for line in out_stream.split('\n'):
            if self.re.match(line):
                self._found = True


    def find(self):
        finder_t = threading.Thread(target=self._find_process)
        finder_t.setDaemon(True)
        finder_t.start()
        finder_t.join()

        process_found = self._found
        self._found = None

        return process_found


class ViberLauncher(threading.Thread):
    """class description"""

    def __init__(self, viber_path="/opt/viber/Viber"):
        super(ViberLauncher, self).__init__()
        self.viber_path = viber_path
        self.setDaemon(True)


    def start(self):
        viber_finder = ProcessFinder(self.viber_path)

        if viber_finder.find():
            raise ViberAlreadyRunning()
        else:
            super(ViberLauncher, self).start()


    def run(self):
        try:
            printf("Launching Viber (%s) ... ", self.viber_path)
            p_viber = subprocess.Popen([self.viber_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            printf("OK\n")

            p_viber.wait()

            printf("Viber process terminated. Quitting...\n")
        except OSError as ose:

            printf("Error starting Viber. Operating System reported: '%s'\n", ose.strerror)

            os.system('pkill -9 Viber')
            os._exit(-1)

        except Exception as ex:

            printf("Error starting Viber because of exception '%s: %s'\n", ex.__class__.__name__, ex.args[0])

            os.system('pkill -9 Viber')
            os._exit(-1)


        try: Gtk.main_quit()
        except: pass


if __name__ == "__main__":

    try:
        arg_close_chat = "--close-chat"               in sys.argv
        arg_use_old    = "--use-old-detection-method" in sys.argv
        arg_use_ext    = "--use-external-detector"    in sys.argv

        viber_window = ViberWindow(close_chat=arg_close_chat, use_old=arg_use_old, use_external=arg_use_ext)

        indicator = AppIndicator.Indicator.new("Viber Indicator", "", AppIndicator.IndicatorCategory.APPLICATION_STATUS)

        ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        indicator.set_icon(VIBER_STATUS_NORMAL)
        indicator.set_attention_icon(icon_notification)

        menu = Gtk.Menu()

        item_open = Gtk.MenuItem("Open Viber")
        item_open.connect("activate", viber_window.open)
        menu.append(item_open)

        sep = Gtk.SeparatorMenuItem()
        menu.append(sep)

        item_exit = gtk.MenuItem("Exit")
        item_exit.connect("activate", viber_window.quit)
        menu.append(item_exit)

        menu.show_all()
        indicator.set_menu(menu)

        t_vipoller = ViberIconPoller(viber_window)
        t_vipoller.setDaemon(True)
        t_vipoller.start()

        GObject.threads_init()
        Gtk.main()

    except ViberAlreadyRunning:

        sys.stdout.write("Viber Already Running!\n")
        sys.stdout.flush()

    except Exception as e:

        printf("Exiting because of exception '%s: %s'\n", e.__class__.__name__, e.args[0])
        os.system('pkill -9 Viber')
        os._exit(-1)

    finally:

        os._exit(0)
