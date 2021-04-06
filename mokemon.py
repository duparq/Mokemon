#!/usr/bin/python3

# Copyright 2021 Christophe Duparquet
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Based on key-mon-1.17 by Scott Kirkwood

"""
Mokemon: mouse and keyboard monitor (for screencasting).
"""


import logging
logging.basicConfig( level=0, format='%(filename)s:%(lineno)d: %(message)s' )
info = logging.info


import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import GdkPixbuf

import math
import os
import time
import xlib


#  Draw pixbuf p1 over pixbuf p0, result in p0.
#
def merge_pixbuf ( p0, p1 ):
  p1.composite( p0,
                0, 0, p0.props.width, p0.props.height,  # x, y, w, h
                0, 0,                                   # offset x, y
                1.0, 1.0,                               # scale x, y
                GdkPixbuf.InterpType.BILINEAR, 255 )


#  Create a transparent window
#
class TransparentWindow(Gtk.Window):
  def __init__(self,**args):
    Gtk.Window.__init__(self,**args)
    screen = self.get_screen()
    visual = screen.get_rgba_visual()
    if visual and screen.is_composited():
      self.set_visual(visual)
    self.set_app_paintable(True)


#  Modifier key image from a SVG file
#
class Modifier(Gtk.Image):
  def __init__(self,box,svg):
    Gtk.Image.__init__(self,file=svg)
    self.tohide = False ;
    box.add( self )

  #  Toggle show / tohide
  #
  def set(self,s):
    if s:
      self.show()
    else:
      self.tohide = True


class App:
  def __init__(self):

    self.show_all_keys = True

    #  Used paths are relative to this file's directory
    #
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    #  A transparent window for the app icon over the desktop
    #
    self.iconwindow = TransparentWindow( accept_focus=False,
                                     resizable=False,
                                     decorated=False,
                                     skip_taskbar_hint=True )
    cssProvider = Gtk.CssProvider()
    cssProvider.load_from_path("mokemon.css")
    Gtk.StyleContext.add_provider_for_screen(self.iconwindow.get_screen(),
                                             cssProvider,
                                             Gtk.STYLE_PROVIDER_PRIORITY_USER);
    self.iconwindow.set_keep_above(True)

    self.iconwindow.add( Gtk.Image(file='svg/mouse-svg.svg') ) # Icon

    self.iconwindow.connect('button-press-event', self.on_iconbtnpress)
    self.iconwindow.connect('button-release-event', self.on_iconbtnrelease)
    self.iconwindow.show_all()

    #  A transparent window for the splashes over the desktop
    #
    self.splash = TransparentWindow( accept_focus=False,
                                     resizable=False,
                                     decorated=False,
                                     skip_taskbar_hint=True )
    self.splash.set_keep_above(True)
    self.splash.show()
    self.hbox = Gtk.HBox(homogeneous=False, spacing=0)
    self.splash.add( self.hbox )
    self.hbox.show()

    self.modifiers = {}
    self.modifiers['ALT'] = Modifier(self.hbox,'svg/alt.svg')
    self.modifiers['ALTGR'] = Modifier(self.hbox,'svg/altgr.svg')
    self.modifiers['CONTROL'] = Modifier(self.hbox,'svg/ctrl.svg')
    self.modifiers['SHIFT'] = Modifier(self.hbox,'svg/shift.svg')
    self.modifiers['CAPSLOCK'] = Modifier(self.hbox,'svg/capslock.svg')

    #  Splash window placement
    #
    self.cx = 1
    self.cy = 0
    self.rx = 1
    self.ry = 0

    #  A rectangle for splash window placement debugging
    #
    # self.splash_rect = Gtk.Image()
    # self.hbox.add( self.splash_rect )
    # with open('svg/rect.svg', 'r') as src:
    #   self.svg_rect = src.read()

    # svg = self.svg_rect.replace('<line/>',
    #                             '<line x1="%s" y1="%d" x2="%d" y2="%d" />' \
    #                             % (self.p0x, self.p0y, self.p1x, self.p1y) )
    # loader = GdkPixbuf.PixbufLoader()
    # loader.write(svg.encode())
    # loader.close()
    # self.splash_rect.set_from_pixbuf( loader.get_pixbuf() )

    self.splash_mouse = Gtk.Image()
    self.hbox.add( self.splash_mouse )

    self.splash_key = Gtk.Image()
    self.hbox.add( self.splash_key )

    #  Dictionnary of pixbufs for temporarily displayed keys
    #
    self.pixbufs = {}
    self.pixbufs["KEY_BACKSPACE"] = Gtk.Image(file='svg/backspace.svg').get_pixbuf()
    self.pixbufs["KEY_ESCAPE"] = Gtk.Image(file='svg/esc.svg').get_pixbuf()
    self.pixbufs["KEY_TAB"] = Gtk.Image(file='svg/tab.svg').get_pixbuf()

    self.pixbufs["KEY_INSERT"] = Gtk.Image(file='svg/inser.svg').get_pixbuf()
    self.pixbufs["KEY_DELETE"] = Gtk.Image(file='svg/delete.svg').get_pixbuf()
    self.pixbufs["KEY_HOME"] = Gtk.Image(file='svg/home.svg').get_pixbuf()
    self.pixbufs["KEY_END"] = Gtk.Image(file='svg/end.svg').get_pixbuf()
    self.pixbufs["KEY_PRIOR"] = Gtk.Image(file='svg/pageup.svg').get_pixbuf()
    self.pixbufs["KEY_PAGE_DOWN"] = Gtk.Image(file='svg/pagedn.svg').get_pixbuf()

    self.pixbufs["KEY_LEFT"] = Gtk.Image(file='svg/left.svg').get_pixbuf()
    self.pixbufs["KEY_UP"] = Gtk.Image(file='svg/up.svg').get_pixbuf()
    self.pixbufs["KEY_RIGHT"] = Gtk.Image(file='svg/right.svg').get_pixbuf()
    self.pixbufs["KEY_DOWN"] = Gtk.Image(file='svg/down.svg').get_pixbuf()

    self.pixbuf_mouse = Gtk.Image(file='svg/mouse.svg').get_pixbuf()
    self.pixbuf_mouseleft1 = Gtk.Image(file='svg/mouse-left-1.svg').get_pixbuf()
    self.pixbuf_mouseleft2 = Gtk.Image(file='svg/mouse-left-2.svg').get_pixbuf()
    self.pixbuf_mouseleft3 = Gtk.Image(file='svg/mouse-left-3.svg').get_pixbuf()
    self.pixbuf_mousemiddle1 = Gtk.Image(file='svg/mouse-middle-1.svg').get_pixbuf()
    self.pixbuf_mouseright1 = Gtk.Image(file='svg/mouse-right-1.svg').get_pixbuf()
    self.pixbuf_mousefwd = Gtk.Image(file='svg/mouse-fwd.svg').get_pixbuf()
    self.pixbuf_mousebwd = Gtk.Image(file='svg/mouse-bwd.svg').get_pixbuf()
    
    with open('svg/key.svg', 'r') as src:
      self.svg_key = src.read()

    #  Initialize variables
    #
    foo,x,y = self.iconwindow.get_display().get_default_seat().get_pointer().get_position()

    self.mousepos = (x,y)
    self.dragstate = 0
    self.btntimes = []
    self.keytime = 0

    #  Listen to window events
    #
    self.splash.connect('check-resize', self.check_resize)
    self.listener = xlib.XEventsListener()
    self.listener.start()
    GLib.idle_add(self.on_idle)

  #  Return True if there are active modifiers (shown)
  #
  def has_active_modifiers(self):
    for k in self.modifiers:
      m = self.modifiers[k]
      if m.props.visible:
        return True
    return False

  def on_iconbtnpress(self, widget, ev): # GdkEventButton
    #info(str(ev)+" %d %d " % (ev.button, ev.state) )
    if ev.button == 1:
      n,x,y,m = ev.window.get_device_position(ev.device)
      #info("DRAGXY: %d %d " % (x,y) )
      self.dragxy = (x,y) # Position of the pointer relative to the icon window
      self.dragstate = 1
    return True

  def on_iconbtnrelease(self, widget, ev):
    if ev.button == 1 and self.dragstate < 2:
      #info("DRAG %d" % self.dragstate)
      exit(0)
    self.dragstate = 0
    return True


  #  Set the position of the splash window somewhere around the mouse pointer
  #
  def check_resize(self, foo=0):
    OFF = 20
    x, y = self.mousepos
    w, h = self.splash.get_size()

    # svg = self.svg_rect.replace('<line/>',
    #                             '<line x1="24" y1="24" x2="%d" self.ry="%d" />' \
    #                             % (24+24*self.rx,24+24*self.ry) )
    # loader = GdkPixbuf.PixbufLoader()
    # loader.write(svg.encode())
    # loader.close()
    # self.splash_rect.set_from_pixbuf( loader.get_pixbuf() )

    #info("self.rx=%d self.ry=%d" % (10*self.rx,10*self.ry))

    if self.rx == 0 or abs(self.ry / self.rx) <= 1:
      if self.rx >= 0:
        # info("CASE 1")
        self.splash.move( x-w-OFF, y-h/2-(h/2+OFF)*(self.ry/self.rx) )
      else:
        # info("CASE 2")
        self.splash.move( x  +OFF, y-h/2+(h/2+OFF)*(self.ry/self.rx) )
    else:
      if self.ry >= 0:
        # info("CASE 3")
        self.splash.move( x-w/2-(w/2+OFF)*(self.rx/self.ry), y-h-OFF )
      else:
        # info("CASE 4")
        self.splash.move( x-w/2+(w/2+OFF)*(self.rx/self.ry), y  +OFF )


  #  Find a pixbuf for the given key code
  #
  def setpixbuf(self,code,doit):
    #
    #  Normal keys: create a pixbuf from an SVG code file
    #
    if code.startswith('KEY_') and	\
         len(code)==5 and		\
         code[4]>="A" and		\
         code[4]<="Z":
      if self.show_all_keys or self.has_active_modifiers():
        if doit:
          svg = self.svg_key.replace('</text>',code[4]+'</text>')
          loader = GdkPixbuf.PixbufLoader()
          loader.write(svg.encode())
          loader.close()
          self.pixbuf = loader.get_pixbuf()
        return True
    #
    #  Process special keys
    #
    for k in list(self.pixbufs):
      if code.startswith(k):
        self.pixbuf = self.pixbufs[k]
        return True
    return False

  
  #  Process window events (X Window)
  #
  def on_idle(self):
    t = time.time()
    ev = self.listener.next()
    if ev:
      if ev.type == 'EV_MOV':

        x, y = ev.value
        ox, oy = self.mousepos

        #info("MOVE %d ( %d, %d ) -> (%d,%d)" % (self.dragstate, ox, oy, x, y))
        self.mousepos = ev.value
        if self.dragstate > 0:
          #
          #  Move the icon window
          #
          self.dragstate += 1
          mx, my = self.dragxy
          self.iconwindow.move( x-mx, y-my )
          return True

        #  Compute the motion of the splash window
        #    Apply a low-pass filter on cumulative movements
        #
        self.cx = (x-ox)*1.0/64 + self.cx*63.0/64
        self.cy = (y-oy)*1.0/64 + self.cy*63.0/64

        #    Compute the y and x ratios in the range -1.0 .. +1.0 (sine, cosine)
        #
        r = math.sqrt( self.cx*self.cx + self.cy*self.cy )
        self.rx = self.cx/r
        self.ry = self.cy/r

        self.check_resize()

      elif ev.type == 'EV_KEY':
        #
        #  Modifiers, displayed until they are released
        #
        if ev.code.startswith('KEY_ALT'):
          self.modifiers['ALT'].set(ev.value)
        elif ev.code == 'KEY_ISO_LEVEL3_SHIFT':
          self.modifiers['ALTGR'].set(ev.value)
        elif ev.code.startswith('KEY_CONTROL'):
          self.modifiers['CONTROL'].set(ev.value)
        elif ev.code.startswith('KEY_SHIFT'):
          self.modifiers['SHIFT'].set(ev.value)
        elif ev.code.startswith('KEY_CAPS_LOCK'):
          self.modifiers['CAPSLOCK'].set(ev.value)
        #
        #  Normal keys, displayed temporarily
        #
        elif self.setpixbuf(ev.code,ev.value):
          if ev.value == 1:
            self.splash_key.set_from_pixbuf(self.pixbuf)
            self.splash_key.show()
            self.keytime = t
        #
        #  Mouse buttons
        #
        elif ev.code.startswith('BTN_LEFT'):
          if ev.value == 1:
            p0 = self.pixbuf_mouse.copy()
            if len(self.btntimes)==2 and t-self.btntimes[0] < 0.2:
              self.btntimes.append(t)
              p1 = self.pixbuf_mouseleft2
            elif len(self.btntimes)==4 and t-self.btntimes[2] < 0.2:
              self.btntimes.append(t)
              p1 = self.pixbuf_mouseleft3
            else:
              self.btntimes = [t]
              p1 = self.pixbuf_mouseleft1
            merge_pixbuf( p0, p1 )
            self.splash_mouse.set_from_pixbuf(p0)
            self.splash_mouse.show()
          else:
            self.btntimes.append(t)
        elif ev.code.startswith('BTN_MIDDLE'):
          if ev.value == 1:
            self.btntimes = [t]
            p0 = self.pixbuf_mouse.copy()
            p1 = self.pixbuf_mousemiddle1
            merge_pixbuf( p0, p1 )
            self.splash_mouse.set_from_pixbuf(p0)
            self.splash_mouse.show()
          else:
            self.btntimes.append(t)
        elif ev.code.startswith('BTN_RIGHT'):
          if ev.value == 1:
            self.btntimes = [t]
            p0 = self.pixbuf_mouse.copy()
            p1 = self.pixbuf_mouseright1
            merge_pixbuf( p0, p1 )
            self.splash_mouse.set_from_pixbuf(p0)
            self.splash_mouse.show()
          else:
            self.btntimes.append(t)
        else:
          info(ev)
      #
      #  Mouse wheel
      #
      elif ev.type == 'EV_REL':
        if ev.code.startswith('REL_WHEEL'):
          if ev.value == 1:
            self.btntimes = [t, t+0.1]
            p0 = Gtk.Image(file='svg/mouse.svg').get_pixbuf()
            p1 = self.pixbuf_mousefwd
            merge_pixbuf( p0, p1 )
            self.splash_mouse.set_from_pixbuf(p0)
            self.splash_mouse.show()
          elif ev.value == -1:
            self.btntimes = [t, t+0.1]
            p0 = Gtk.Image(file='svg/mouse.svg').get_pixbuf()
            p1 = self.pixbuf_mousebwd
            merge_pixbuf( p0, p1 )
            self.splash_mouse.set_from_pixbuf(p0)
            self.splash_mouse.show()
      #
      #  Unknown
      #
      else:
        info(ev)
      return True

    #  Hide mouse after a delay
    #
    if len(self.btntimes)%2 == 0 and \
       len(self.btntimes)>0 and \
       t-self.btntimes[-2] > 0.33:
      self.splash_mouse.hide()
      self.btntimes=[]
      return True

    #  Hide key after a delay
    #
    if self.keytime>0 and t-self.keytime > 0.33:
      self.splash_key.hide()
      self.keytime = 0

    #  Hide modifiers only when there is no key displayed
    #
    if self.keytime == 0:
      for k in self.modifiers:
        m = self.modifiers[k]
        if m.tohide:
          m.tohide = False
          m.hide()

    time.sleep(0.02)
    return True


if __name__ == '__main__':
  try:
    App()
    Gtk.main()
  except KeyboardInterrupt:
    pass
