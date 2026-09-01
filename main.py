__version__ = "1.0.0"

import os
import re
import json
import math
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput


# ==================================================
# SETTINGS
# ==================================================

COMIC_FOLDER = "/storage/emulated/0/Download/8BitTheater"
LEGACY_STATE_FILE = os.path.join(COMIC_FOLDER, "_reader_state.json")

IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
)

MAX_ZOOM = 5.0
SWIPE_DISTANCE = 120


# ==================================================
# ANDROID STORAGE ACCESS
# ==================================================

def has_storage_access():
    """
    Android 11+ requires special "All files access" for direct
    file-path access to shared storage such as Downloads.

    This APK is intended as a personal sideloaded reader.
    """
    if platform != "android":
        return True

    try:
        from jnius import autoclass

        BuildVersion = autoclass("android.os.Build$VERSION")
        Environment = autoclass("android.os.Environment")

        if BuildVersion.SDK_INT >= 30:
            return bool(Environment.isExternalStorageManager())

        return True

    except Exception as error:
        print("Could not check storage access:", error)
        return False


def open_storage_settings():
    """
    Open Android's per-app "All files access" settings page.
    """
    if platform != "android":
        return

    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")

        activity = PythonActivity.mActivity
        package_name = activity.getPackageName()

        intent = Intent()
        intent.setAction(
            Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION
        )
        intent.setData(
            Uri.parse("package:" + package_name)
        )

        activity.startActivity(intent)

    except Exception as error:
        print("Could not open per-app storage settings:", error)

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")

            activity = PythonActivity.mActivity

            intent = Intent()
            intent.setAction(
                Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION
            )

            activity.startActivity(intent)

        except Exception as fallback_error:
            print(
                "Could not open storage settings:",
                fallback_error
            )


# ==================================================
# FIND COMICS
# ==================================================

def find_comics():

    if not os.path.isdir(COMIC_FOLDER):
        return []

    pattern = re.compile(
        r"^(\d{4})\s*-\s*(.+)"
    )

    comics_by_number = {}

    for filename in os.listdir(COMIC_FOLDER):

        if not filename.lower().endswith(
            IMAGE_EXTENSIONS
        ):
            continue

        match = pattern.match(filename)

        if not match:
            continue

        number = int(match.group(1))

        full_path = os.path.join(
            COMIC_FOLDER,
            filename
        )

        if number not in comics_by_number:

            comics_by_number[number] = (
                full_path
            )

        else:

            old_filename = os.path.basename(
                comics_by_number[number]
            )

            # Prefer the more descriptive filename.
            if len(filename) > len(old_filename):

                comics_by_number[number] = (
                    full_path
                )

    comics = []

    for number in sorted(
        comics_by_number.keys()
    ):

        path = comics_by_number[number]

        filename = os.path.basename(path)

        title = os.path.splitext(
            filename
        )[0]

        title = re.sub(
            r"^\d{4}\s*-\s*",
            "",
            title
        )

        comics.append({
            "number": number,
            "title": title,
            "path": path,
        })

    return comics


# ==================================================
# GESTURE-AWARE SCROLL VIEW
# ==================================================

class ComicScrollView(ScrollView):

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        self.reader = None
        self.image_widget = None

        self.active_touches = {}

        self.pinch_start_distance = None
        self.pinch_start_width = None

        self.was_pinching = False

        self.swipe_start_x = None
        self.swipe_start_y = None


    def update_image_height(self):

        if not self.image_widget:
            return

        texture = self.image_widget.texture

        if not texture:
            return

        if texture.width <= 0:
            return

        ratio = (
            texture.height
            /
            texture.width
        )

        self.image_widget.height = (
            self.image_widget.width
            *
            ratio
        )


    def reset_zoom(self):

        if not self.image_widget:
            return

        if self.width <= 0:
            return

        self.image_widget.width = self.width

        self.update_image_height()

        self.scroll_x = 0.5
        self.scroll_y = 1


    def get_zoom(self):

        if not self.image_widget:
            return 1.0

        if self.width <= 0:
            return 1.0

        return (
            self.image_widget.width
            /
            self.width
        )


    def on_touch_down(self, touch):

        if not self.collide_point(*touch.pos):

            return super().on_touch_down(
                touch
            )

        # Double-tap returns to fit-to-screen.
        if touch.is_double_tap:

            self.reset_zoom()

            return True

        self.active_touches[
            touch.uid
        ] = touch

        if len(self.active_touches) == 1:

            self.swipe_start_x = touch.x
            self.swipe_start_y = touch.y

            self.was_pinching = False

        elif len(self.active_touches) == 2:

            touches = list(
                self.active_touches.values()
            )

            self.pinch_start_distance = (
                self.distance_between(
                    touches[0],
                    touches[1]
                )
            )

            if self.image_widget:

                self.pinch_start_width = (
                    self.image_widget.width
                )

            self.was_pinching = True

            self.do_scroll_x = False
            self.do_scroll_y = False

        return super().on_touch_down(
            touch
        )


    def on_touch_move(self, touch):

        if touch.uid in self.active_touches:

            self.active_touches[
                touch.uid
            ] = touch

        if (
            len(self.active_touches) >= 2
            and
            self.pinch_start_distance
            and
            self.pinch_start_width
        ):

            touches = list(
                self.active_touches.values()
            )

            current_distance = (
                self.distance_between(
                    touches[0],
                    touches[1]
                )
            )

            if current_distance <= 0:
                return True

            scale_change = (
                current_distance
                /
                self.pinch_start_distance
            )

            new_width = (
                self.pinch_start_width
                *
                scale_change
            )

            minimum_width = self.width

            maximum_width = (
                self.width
                *
                MAX_ZOOM
            )

            new_width = max(
                minimum_width,
                min(
                    new_width,
                    maximum_width
                )
            )

            self.image_widget.width = (
                new_width
            )

            self.update_image_height()

            return True

        return super().on_touch_move(
            touch
        )


    def on_touch_up(self, touch):

        is_tracked = (
            touch.uid
            in self.active_touches
        )

        navigate = False

        if (
            is_tracked
            and
            not self.was_pinching
            and
            self.swipe_start_x is not None
        ):

            dx = (
                touch.x
                -
                self.swipe_start_x
            )

            dy = (
                touch.y
                -
                self.swipe_start_y
            )

            # At normal zoom, horizontal swipe changes comic.
            # While zoomed, horizontal movement pans the image.
            if self.get_zoom() <= 1.10:

                if (
                    abs(dx) >= SWIPE_DISTANCE
                    and
                    abs(dx) > abs(dy) * 1.5
                ):

                    navigate = True

                    if dx < 0:

                        if self.reader:

                            self.reader.next_comic(
                                None
                            )

                    else:

                        if self.reader:

                            self.reader.previous_comic(
                                None
                            )

        if is_tracked:

            del self.active_touches[
                touch.uid
            ]

        if len(self.active_touches) < 2:

            self.do_scroll_x = True
            self.do_scroll_y = True

            self.pinch_start_distance = None
            self.pinch_start_width = None

        if len(self.active_touches) == 0:

            self.swipe_start_x = None
            self.swipe_start_y = None

            self.was_pinching = False

        if navigate:
            return True

        return super().on_touch_up(
            touch
        )


    def distance_between(
        self,
        touch1,
        touch2
    ):

        return math.hypot(
            touch1.x - touch2.x,
            touch1.y - touch2.y
        )


# ==================================================
# MAIN APP
# ==================================================

class ComicReader(App):

    def build(self):

        self.title = "8-Bit Theater Reader"

        Window.softinput_mode = (
            "below_target"
        )

        self.state_file = os.path.join(
            self.user_data_dir,
            "reader_state.json"
        )

        self.root_box = BoxLayout(
            orientation="vertical"
        )

        self.load_correct_screen()

        return self.root_box


    def load_correct_screen(self):

        self.root_box.clear_widgets()

        if not has_storage_access():

            self.show_permission_screen()

            return

        self.build_reader_screen()


    def show_permission_screen(self):

        box = BoxLayout(
            orientation="vertical",
            spacing=20,
            padding=30
        )

        label = Label(
            text=(
                "8-Bit Theater Reader needs permission "
                "to read the comics already stored in:\n\n"
                "/Download/8BitTheater\n\n"
                "Tap the button below, enable "
                "\"Allow access to manage all files\", "
                "then return to the reader."
            ),
            halign="center",
            valign="middle"
        )

        label.bind(
            size=lambda instance, value:
                setattr(
                    instance,
                    "text_size",
                    (value[0], None)
                )
        )

        box.add_widget(label)

        button = Button(
            text="Grant File Access",
            size_hint_y=None,
            height=70
        )

        button.bind(
            on_release=lambda instance:
                open_storage_settings()
        )

        box.add_widget(button)

        retry_button = Button(
            text="I Granted Access - Try Again",
            size_hint_y=None,
            height=60
        )

        retry_button.bind(
            on_release=lambda instance:
                self.load_correct_screen()
        )

        box.add_widget(retry_button)

        self.root_box.add_widget(box)


    def build_reader_screen(self):

        self.comics = find_comics()

        self.current_index = 0

        if not self.comics:

            box = BoxLayout(
                orientation="vertical",
                spacing=15,
                padding=20
            )

            box.add_widget(
                Label(
                    text=(
                        "No comics were found.\n\n"
                        "Expected folder:\n"
                        + COMIC_FOLDER
                        + "\n\n"
                        "Make sure the folder and comic "
                        "files still exist."
                    )
                )
            )

            retry = Button(
                text="Scan Again",
                size_hint_y=None,
                height=60
            )

            retry.bind(
                on_release=lambda instance:
                    self.load_correct_screen()
            )

            box.add_widget(retry)

            self.root_box.add_widget(box)

            return

        self.number_lookup = {}

        for index, comic in enumerate(
            self.comics
        ):

            self.number_lookup[
                comic["number"]
            ] = index


        root = BoxLayout(
            orientation="vertical",
            spacing=4,
            padding=4
        )


        # TITLE
        self.title_label = Label(
            text="",
            size_hint_y=None,
            height=55,
            font_size=17
        )

        root.add_widget(
            self.title_label
        )


        # COMIC VIEW
        self.scroll = ComicScrollView(
            do_scroll_x=True,
            do_scroll_y=True
        )

        self.scroll.reader = self

        self.comic_image = Image(
            size_hint=(
                None,
                None
            ),
            allow_stretch=True,
            keep_ratio=True
        )

        self.scroll.image_widget = (
            self.comic_image
        )

        self.comic_image.bind(
            texture=self.image_loaded
        )

        self.scroll.add_widget(
            self.comic_image
        )

        root.add_widget(
            self.scroll
        )


        # PREVIOUS / COUNTER / NEXT
        navigation = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=60,
            spacing=5
        )

        self.previous_button = Button(
            text="< Previous",
            font_size=17
        )

        self.previous_button.bind(
            on_release=self.previous_comic
        )

        navigation.add_widget(
            self.previous_button
        )

        self.counter_label = Label(
            text="",
            font_size=16,
            size_hint_x=0.6
        )

        navigation.add_widget(
            self.counter_label
        )

        self.next_button = Button(
            text="Next >",
            font_size=17
        )

        self.next_button.bind(
            on_release=self.next_comic
        )

        navigation.add_widget(
            self.next_button
        )

        root.add_widget(
            navigation
        )


        # JUMP
        jump_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=55,
            spacing=5
        )

        jump_label = Label(
            text="Comic #:",
            size_hint_x=0.35
        )

        jump_row.add_widget(
            jump_label
        )

        self.jump_input = TextInput(
            multiline=False,
            input_filter="int",
            hint_text="Example: 500",
            font_size=18
        )

        self.jump_input.bind(
            on_text_validate=
                self.jump_to_comic
        )

        jump_row.add_widget(
            self.jump_input
        )

        jump_button = Button(
            text="Jump",
            size_hint_x=0.4
        )

        jump_button.bind(
            on_release=self.jump_to_comic
        )

        jump_row.add_widget(
            jump_button
        )

        root.add_widget(
            jump_row
        )


        # SMALL GESTURE HELP
        instruction_label = Label(
            text=(
                "Swipe left/right to change comic   "
                "Pinch to zoom   "
                "Double-tap to reset"
            ),
            size_hint_y=None,
            height=35,
            font_size=12
        )

        root.add_widget(
            instruction_label
        )


        self.root_box.add_widget(root)

        self.load_position()

        Clock.schedule_once(
            lambda dt:
                self.show_comic(
                    self.current_index
                ),
            0.2
        )


    def on_resume(self):

        # Returning from Android settings lands here.
        Clock.schedule_once(
            lambda dt:
                self.load_correct_screen()
                if has_storage_access()
                and not hasattr(
                    self,
                    "comic_image"
                )
                else None,
            0.25
        )


    def image_loaded(
        self,
        *args
    ):

        Clock.schedule_once(
            lambda dt:
                self.scroll.reset_zoom(),
            0.05
        )


    def show_comic(
        self,
        index
    ):

        if index < 0:
            index = 0

        if index >= len(self.comics):

            index = (
                len(self.comics) - 1
            )

        self.current_index = index

        comic = self.comics[index]

        self.comic_image.source = (
            comic["path"]
        )

        self.comic_image.reload()

        self.title_label.text = (
            f"{comic['number']:04d} - "
            f"{comic['title']}"
        )

        self.counter_label.text = (
            f"{index + 1}"
            f" / "
            f"{len(self.comics)}"
        )

        self.previous_button.disabled = (
            index == 0
        )

        self.next_button.disabled = (
            index
            ==
            len(self.comics) - 1
        )

        Clock.schedule_once(
            lambda dt:
                self.reset_comic_view(),
            0.15
        )

        self.save_position()


    def reset_comic_view(self):

        self.scroll.reset_zoom()

        self.scroll.scroll_y = 1
        self.scroll.scroll_x = 0.5


    def next_comic(
        self,
        instance
    ):

        if (
            self.current_index
            <
            len(self.comics) - 1
        ):

            self.show_comic(
                self.current_index + 1
            )


    def previous_comic(
        self,
        instance
    ):

        if self.current_index > 0:

            self.show_comic(
                self.current_index - 1
            )


    def jump_to_comic(
        self,
        instance
    ):

        text = (
            self.jump_input.text.strip()
        )

        if not text:
            return

        try:

            number = int(text)

        except ValueError:
            return

        if number in self.number_lookup:

            self.show_comic(
                self.number_lookup[
                    number
                ]
            )

            self.jump_input.text = ""

        else:

            self.title_label.text = (
                f"Comic {number} "
                f"was not found."
            )


    def save_position(self):

        comic = self.comics[
            self.current_index
        ]

        state = {
            "comic_number":
                comic["number"]
        }

        try:

            with open(
                self.state_file,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    state,
                    file
                )

        except Exception as error:

            print(
                "Could not save position:",
                error
            )


    def load_position(self):

        # Prefer the standalone app's private state file.
        # On the first run, fall back to the old Pydroid state
        # stored in the comic folder so your place is preserved.
        state_path = self.state_file

        if not os.path.exists(state_path):

            if os.path.exists(LEGACY_STATE_FILE):
                state_path = LEGACY_STATE_FILE
            else:
                self.current_index = 0
                return

        try:

            with open(
                state_path,
                "r",
                encoding="utf-8"
            ) as file:

                state = json.load(file)

            number = state.get(
                "comic_number",
                1
            )

            if number in self.number_lookup:

                self.current_index = (
                    self.number_lookup[
                        number
                    ]
                )

                # Migrate a legacy Pydroid position into
                # the standalone app's private state.
                if state_path == LEGACY_STATE_FILE:
                    self.save_position()

        except Exception as error:

            print(
                "Could not load position:",
                error
            )

            self.current_index = 0


if __name__ == "__main__":

    ComicReader().run()
