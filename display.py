import time
import os
from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.core.virtual import viewport
from luma.led_matrix.device import max7219
from luma.core.legacy import text, show_message
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT, SINCLAIR_FONT, LCD_FONT
from PIL import Image
import time
from helper import make_string_from_list, get_width, get_image_as_list
from datetime import datetime, timedelta
from datetime import time as dtTime
import copy
from line_manager import Line_Manager
from pathlib import Path
from sonos_state import Sonos_State, Sonos_Room
from display_state import display_state


class DisplayDriver():

    def __init__(self, startup_screen=True):
        block_orientation = -90
        rotate = 0
        inreverse = False
        self.width = 64
        height = 16
        self.serial = spi(port=0, device=0, gpio=noop())
        self.device = max7219(self.serial, block_orientation=block_orientation,
                              rotate=rotate or 0, blocks_arranged_in_reverse_order=inreverse,
                              width=self.width, height=height)
        self.device.contrast(0x0)

        self.screens = list()

        self.rolling_frame_counter = 0
        self.last_frame = None

        self.s8_flughafen_minutes_cache = list()
        self.s8_herrsching_minutes_cache = list()
        self.minute_cache = 0
        self.seconds_cache = 0
        self.number_next_connections = 3

        self.refresh_counter = 0
        self.message_counter = 0
        self.playing_screen_counter = 0
        self.state = display_state.startup_screen

        self.last_refresh_cache = datetime.now()
        self.is_sleeping = False
        self.should_sleep = False
        self.sleep_wait_counter = 0

        if startup_screen:
            self.start_up_screen()

    def add_screen(self, screen):
        screen.add_device(self.device)
        self.screens.append(screen)

    def set_brightness(self):
        now_time = datetime.utcnow().time()
        if now_time >= dtTime(17, 30) or now_time <= dtTime(6, 30):
            self.device.contrast(0x0)
        else:
            self.device.contrast(0x70)

    def start_up_screen(self, display_time=2):
        self.state = display_state.startup_screen
        with canvas(self.device) as draw:
                text(draw, (0, 4), "Matrixel",
                    fill="white", font=proportional(CP437_FONT))
        time.sleep(display_time)

    def calc_string_length(self, message):
        # Initialize with the blank spaces between the letters
        length = len(message) - 1
        for letter in message:
            length += self.calc_length_of_letter(letter)
        #print(str(length))
        return length

    def calc_length_of_letter(self, letter):
        #no €, 
        if letter in ["!"]:
            return 1
        if letter in [",", ".", ":", ";", "'"]:
            return 2
        if letter in ["i", "l", "I", str(1), " "]:
            return 3
        elif letter in ["j", "k", "<", ">"]:
            return 4
        else:
            return 5

    def display_minutes(self, draw, departures: list, cache, x, y):
        for departure in departures:
            minute = departure.minutes()
            width = get_width(minute)
            #print(str(minute) + ": " + str(x) + "/" + str(y))
            text(draw, (x, y), str(minute),
                fill="white", font=proportional(LCD_FONT))
            x += width + 1
            draw.point([x, y+5, x, y+6], fill="white")
            text(draw, (x, y), " ",
                    fill="white", font=proportional(LCD_FONT))
            x += 2
        draw.point([x-3, y, x-2, y, x-3, y+1, x-2, y+1, x-3, y+2, 
                   x-2, y+2, x-3, y+3, x-2, y+3, x-3, y+4, x-2, y+4, 
                   x-3, y+5, x-2, y+5, x-3, y+6, x-2, y+6], fill="black")
        text(draw, (x-3, y), "  ",
                    fill="white", font=proportional(LCD_FONT))

    def check_sleep_mode(self):
        # auto wake up in the morning
        now_time = datetime.now().time()
        if now_time >= dtTime(5, 50, 0) and now_time <= dtTime(5, 50, 3):
            print("must wake up")
            self.should_sleep = False

        if not self.should_sleep and self.is_sleeping:
            self.wake_up()
        return self.should_sleep

    def wake_up(self):
        self.s8_flughafen_minutes_cache = None
        self.s8_herrsching_minutes_cache = None
        self.is_sleeping = False
        self.refresh_counter = 0
        self.message_counter = 0
                
    def sleep_screen(self):
        if not self.is_sleeping:
            self.device.contrast(0x0)
            sleep_file = Path("/home/pi/Documents/mvg_departure_monitor/icons/moon.txt")
            with canvas(self.device) as draw:
                draw.point([63,0], fill="white")
                # draw.point(get_image_as_list(sleep_file, 55, 2), fill="white")
            self.is_sleeping = True
            self.state = display_state.sleeping

    def toggle_sleep_mode(self):
        if self.is_sleeping:
            print("waking up")
            self.should_sleep = False
            return "awaking"
        else:
            print("going to sleep")
            self.should_sleep = True
            return "sleeping"


    def show_idle_state(self):
        minutes_since_last_refresh = None
        self.cur_playing_cache = None
        if self.line_manager.last_refresh():
            minutes_since_last_refresh = datetime.now() - self.line_manager.last_refresh()

        if minutes_since_last_refresh and minutes_since_last_refresh < timedelta(minutes=3):
            self.reset_refresh_counter_at(30*20)
            if self.refresh_counter == 0:
                with canvas(self.device) as draw:
                    draw.point([0, 0], fill="black")
            elif self.refresh_counter == 12 :
                with canvas(self.device) as draw:
                    draw.point([0, 0], fill="white")
        elif not minutes_since_last_refresh or minutes_since_last_refresh > timedelta(minutes=3):
            self.reset_refresh_counter_at(20)
            if self.refresh_counter == 0:
                with canvas(self.device) as draw:
                    draw.point([0, 0], fill="black")
            elif self.refresh_counter == 12 :
                with canvas(self.device) as draw:
                    draw.point([0, 0], fill="white")
        else:
            with canvas(self.device) as draw:
                draw.point([0, 0], fill="white")
        self.refresh_counter += 1
        self.state = display_state.idle

    def reset_refresh_counter_at(self, number):
        if self.refresh_counter >= number:
            self.refresh_counter = 0

    def check_refresh(self, last_refresh):
        if not last_refresh:
            return False
        refresh_successfull = last_refresh != self.last_refresh_cache
        self.last_refresh_cache = last_refresh
        return refresh_successfull

    def draw_city_line(self, draw, s8_herrsching_minutes):
        draw.point(get_image_as_list(
            "/home/pi/Documents/mvg_departure_monitor/icons/frauenkirche.txt", 0, 0), fill="white")
        self.display_minutes(draw, s8_herrsching_minutes, self.s8_herrsching_minutes_cache, 9, 0)

    def draw_airport_line(self, draw, s8_flughafen_minutes):
        draw.point(get_image_as_list(
            "/home/pi/Documents/mvg_departure_monitor/icons/airplane.txt", 0, 8), fill="white")
        self.display_minutes(draw, s8_flughafen_minutes, self.s8_flughafen_minutes_cache, 9, 9)

    def write_first_line(self, data):
        with canvas(self.device) as draw:
            text(draw, (0, 0), data, fill="white", font=proportional(TINY_FONT))

    def write_second_line(self, data):
        with canvas(self.device) as draw:
            text(draw, (0, 8), data, fill="white", font=proportional(LCD_FONT))

    def check_new_message(self):
        possibly_new_message = self.msg_manager.get_newest_message()
        #print(str(possibly_new_message)+ "has new message: " + str(self.msg_manager.has_new_message()))
        if self.msg_manager.has_new_message():
            self.new_message = False
            if id(possibly_new_message) != id(self.cur_msg_cache):
                self.cur_msg_cache = possibly_new_message
                print("new message")
                self.new_message = True
            return True
        else:
            if self.cur_msg_cache:
                self.wake_up()
            self.cur_msg_cache = None
            return False

    def display_message(self):
        self.set_brightness()
        self.refresh_counter = 0
        self.message_counter += 1
        msg_length = self.cur_msg_cache.length
        text_begin = 0
        if self.new_message:
            self.message_counter = 0
        if msg_length > self.width:
            animation_delay = 35
            if self.message_counter > animation_delay:
                #rint("message counter in if: " + str(self.message_counter))
                text_begin = animation_delay - self.message_counter
            if text_begin < (-msg_length - 7):
                #print("true!")
                self.message_counter = 0
        #print("textbegin: " + str(text_begin))
        if (msg_length > self.width) or self.new_message:
            with canvas(self.device) as draw:
                text(draw, (0, 0), self.cur_msg_cache.username,
                    fill="white", font=proportional(CP437_FONT))
                try:
                    text(draw, (text_begin, 9), self.cur_msg_cache.message,
                        fill="white", font=proportional(LCD_FONT))
                except IndexError as e:
                    print(str(e))
                    pass

    def playing_screen(self):
        playing_rooms = self.sonos_state.get_playing_rooms()
        self.refresh_counter = 0
        self.state = display_state.playing
        if playing_rooms:
            #print("playing screen started, sonos_changed: " + str(self.sonos_changed))
            self.playing_screen_counter += 1
            title_length = self.calc_string_length(list(playing_rooms.values())[0].current_track.name)
            artist_length = self.calc_string_length(list(playing_rooms.values())[0].current_track.artist)
            if artist_length > title_length:
                display_string_length = artist_length
            else:
                display_string_length = title_length
            text_begin = 0
            if self.sonos_changed:
                self.playing_screen_counter = 0
            if display_string_length > self.width:
                animation_delay = 60
                if self.playing_screen_counter > animation_delay:
                    #print("message counter in if: " + str(self.message_counter))
                    text_begin = animation_delay - self.playing_screen_counter
                if text_begin < (-display_string_length - 7):
                    #print("true!")
                    self.playing_screen_counter = 0
            if (display_string_length > self.width) or self.sonos_changed:
                upper_shift = text_begin if title_length > self.width else 0
                lower_shift = text_begin if artist_length > self.width else 0
                with canvas(self.device) as draw:
                    text(draw, (upper_shift, 0), list(playing_rooms.values())[0].current_track.name,
                            fill="white", font=proportional(LCD_FONT))
                    text(draw, (lower_shift, 9), list(playing_rooms.values())[0].current_track.artist,
                        fill="white", font=proportional(LCD_FONT))

    def check_playing_screen(self):
        if self.sonos_state.any_room_is_playing():
            #print(str(self.cur_playing_cache))
            #if isinstance(self.cur_playing_cache, Sonos_Room):
            #   print("cache: " + self.cur_playing_cache.current_track.name + ", now: " + list(self.sonos_state.get_playing_rooms().values())[0].current_track.name)
            if not isinstance(self.cur_playing_cache, Sonos_Room) or (self.cur_playing_cache.current_track.name != list(self.sonos_state.get_playing_rooms().values())[0].current_track.name):
                #print("sonos changed")
                self.sonos_changed = True
                self.cur_playing_cache = copy.deepcopy(list(self.sonos_state.get_playing_rooms().values())[0])
                return True
            self.sonos_changed = False
            return True
        return False

    def departures_screen(self):
        self.state = display_state.departures
        s8_flughafen_minutes = self.line_manager.get("s8", "flughafen münchen").get_next_connections_excerpt(3)
        s8_herrsching_minutes = self.line_manager.get("s8", "herrsching").get_next_connections_excerpt(3)
        if not ((s8_flughafen_minutes == self.s8_flughafen_minutes_cache) and
                s8_herrsching_minutes == self.s8_herrsching_minutes_cache):
            self.set_brightness()
            self.refresh_counter = 0
            self.s8_flughafen_minutes_cache = s8_flughafen_minutes
            self.s8_herrsching_minutes_cache = s8_herrsching_minutes
            with canvas(self.device) as draw:
                self.draw_city_line(draw, s8_herrsching_minutes)
                self.draw_airport_line(draw, s8_flughafen_minutes)

    def black_screen(self):
        if not self.state == display_state.black:
            #print("blacked")
            self.device.clear()
            self.state = display_state.black

    def refresh_screen_priorities(self):
        for screen in self.screens:
            screen.refresh_priority()

    def display_highest_priority_screen(self):
        if self.screens:
            self.get_highest_priority_screen().display(self.rolling_frame_counter, self.last_frame)

    def get_highest_priority_screen(self):
        if self.screens:
            return sorted(self.screens, key= lambda x: x.priority)[0]
        else:
            return None

    def set_screen_environment(self):
        self.rolling_frame_counter += 1
        if self.rolling_frame_counter >= 999999999:
            self.rolling_frame_counter = 0
        self.last_frame = self.get_highest_priority_screen()
            
    def main_layout(self):
        s_bahn_active = False
        if self.check_new_message():
            self.display_message()
            return
        if self.check_sleep_mode():
            self.sleep_screen()
            return
        if self.check_playing_screen():
            self.playing_screen()
            return
        if s_bahn_active and not self.line_manager.check_as_usual():
            self.departures_screen()
            return
        else:
            #self.show_idle_state()
            #print("black")
            self.black_screen()

    def new_main(self):
        self.refresh_screen_priorities()
        self.display_highest_priority_screen()
        self.set_screen_environment()
