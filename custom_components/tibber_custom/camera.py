import datetime
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from dateutil import tz
from homeassistant.components.local_file.camera import LocalFile
from homeassistant.util import dt as dt_util, slugify

_LOGGER = logging.getLogger(__name__)

DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 700

# Define some colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (3, 155, 229)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    Path(hass.config.path("www/")).mkdir(parents=True, exist_ok=True)

    dev = []
    for home in hass.data["tibber"].get_homes(only_active=True):
        if not home.info:
            await home.update_info()
        dev.append(TibberCam(home, hass))
    async_add_entities(dev)

class TibberCam(LocalFile):
    def __init__(self, home, hass):
        self._name = home.info["viewer"]["home"]["appNickname"]
        if self._name is None:
            self._name = home.info["viewer"]["home"]["address"].get("address1", "")
        self._path = hass.config.path(f"www/prices_{self._name}.png")
        self._home = home
        self.hass = hass
        self._cons_data = []
        self._last_update = dt_util.now() - datetime.timedelta(hours=1)
        self.realtime_state = None

        super().__init__(self._name, self._path)

    async def async_camera_image(self, width=None, height=None):
        """Return bytes of camera image."""
        await self._generate_fig(width or DEFAULT_WIDTH, height or DEFAULT_HEIGHT)
        return await self.hass.async_add_executor_job(self.camera_image)

    async def _generate_fig(self, width, height):
        if (dt_util.now() - self._last_update) < datetime.timedelta(minutes=1):
            return

        if (self._home.last_data_timestamp - dt_util.now()).total_seconds() > 11 * 3600:
            await self._home.update_info_and_price_info()

        self._last_update = dt_util.now()
        if self._home.has_real_time_consumption:
            self.realtime_state = self.hass.states.get(
                f"sensor.real_time_consumption_{slugify(self._name)}"
            )
            if self.realtime_state is None:
                self.realtime_state = self.hass.states.get(
                    f"sensor.power_{slugify(self._name)}"
                )
        else:
            self.realtime_state = None

        prices = []
        dates = []
        now = dt_util.now()
        for key, price_total in self._home.price_total.items():
            key = dt_util.as_local(dt_util.parse_datetime(key))
            if key.date() < now.date():
                continue
            prices.append(price_total)
            dates.append(key)

        hour = now.hour
        dt = datetime.timedelta(minutes=now.minute)

        if len(prices) < max(10, hour + 1):
            _LOGGER.warning("No prices")
            return

        # To plot the final hour
        prices.append(prices[-1])
        dates.append(dates[-1] + datetime.timedelta(hours=1))

        # Create a new image with white background
        img = Image.new('RGB', (width, height), WHITE)
        draw = ImageDraw.Draw(img)

        # Define margins and calculate drawing area
        left_margin = 60
        right_margin = 20
        top_margin = 20
        bottom_margin = 40

        plot_width = width - left_margin - right_margin
        plot_height = height - top_margin - bottom_margin

        # Find min and max values for scaling
        min_price = min(prices)
        max_price = max(prices)

        # Normalize and scale dates and prices
        date_min = dates[0]
        date_max = dates[-1]
        date_range = (date_max - date_min).total_seconds()

        # Scale functions
        def scale_x(date):
            return left_margin + (plot_width * (date - date_min).total_seconds() / date_range)

        def scale_y(price):
            return top_margin + plot_height - ((price - min_price) / (max_price - min_price) * plot_height)

        # Draw axis lines
        draw.line([left_margin, top_margin, left_margin, height - bottom_margin], fill=BLACK)
        draw.line([left_margin, height - bottom_margin, width - right_margin, height - bottom_margin], fill=BLACK)

        # Plot price data
        for i in range(len(prices) - 1):
            x1, y1 = scale_x(dates[i]), scale_y(prices[i])
            x2, y2 = scale_x(dates[i + 1]), scale_y(prices[i + 1])
            draw.line([x1, y1, x2, y2], fill=BLUE, width=2)

        # Plot current hour indicator
        draw.line(
            [
                scale_x(dates[hour] + dt),
                scale_y(min(prices) - 0.005),
                scale_x(dates[hour] + dt),
                scale_y(max(prices) + 0.0075),
            ],
            fill=RED,
            width=2,
        )

        # Add text annotations
        font = ImageFont.load_default()
        for i, (date, price) in enumerate(zip(dates, prices)):
            if i % 2 == 0:  # reduce clutter by only annotating every other point
                draw.text((scale_x(date), scale_y(price) - 15), f"{price:.2f}", fill=BLACK, font=font)

        # Save the image asynchronously
        await self.hass.async_add_executor_job(self._save_image, img)

    def _save_image(self, img):
        """Save the image to the file system."""
        img.save(self._path)
