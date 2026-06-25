from django.db import models


class Feed(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-downloaded_at']

    def __str__(self):
        return f"{self.name} ({self.downloaded_at.date()})"


class Agency(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='agencies')
    agency_id = models.CharField(max_length=255, blank=True, default='')
    agency_name = models.CharField(max_length=255)
    agency_url = models.URLField(max_length=500)
    agency_timezone = models.CharField(max_length=255)
    agency_lang = models.CharField(max_length=2, blank=True, default='pt')
    agency_phone = models.CharField(max_length=127, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'agencies'

    def __str__(self):
        return self.agency_name


class Route(models.Model):
    ROUTE_TYPES = (
        (0, 'Tranvia'),
        (1, 'Metro'),
        (2, 'Ferrocarril'),
        (3, 'Ônibus'),
        (4, 'Ferry'),
        (5, 'Teleférico'),
        (6, 'Gôndola'),
        (7, 'Funicular'),
        (11, 'Trolebus'),
        (12, 'Monotrilho'),
    )

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='routes')
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='routes', null=True)
    route_id = models.CharField(max_length=255, db_index=True)
    route_short_name = models.CharField(max_length=63, blank=True, null=True, db_index=True)
    route_long_name = models.CharField(max_length=255, blank=True, null=True)
    route_type = models.PositiveIntegerField(choices=ROUTE_TYPES, default=3)
    route_color = models.CharField(max_length=6, blank=True, null=True)
    route_text_color = models.CharField(max_length=6, blank=True, null=True)
    route_sort_order = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['route_sort_order', 'route_short_name']

    def __str__(self):
        return f"{self.route_short_name} - {self.route_long_name}"


class Stop(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='stops')
    stop_id = models.CharField(max_length=255, db_index=True)
    stop_code = models.CharField(max_length=255, blank=True, null=True)
    stop_name = models.CharField(max_length=255, db_index=True)
    stop_desc = models.TextField(blank=True, null=True)
    stop_lat = models.FloatField(null=True, blank=True)
    stop_lon = models.FloatField(null=True, blank=True)
    location_type = models.PositiveIntegerField(null=True, blank=True)
    parent_station = models.CharField(max_length=255, blank=True, default='')
    wheelchair_boarding = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.stop_name} ({self.stop_id})"


class Calendar(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='calendars')
    service_id = models.CharField(max_length=255, db_index=True)
    monday = models.BooleanField()
    tuesday = models.BooleanField()
    wednesday = models.BooleanField()
    thursday = models.BooleanField()
    friday = models.BooleanField()
    saturday = models.BooleanField()
    sunday = models.BooleanField()
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        verbose_name_plural = 'calendars'

    def __str__(self):
        return self.service_id


class CalendarDate(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='calendar_dates')
    service_id = models.CharField(max_length=255, db_index=True)
    date = models.DateField()
    exception_type = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.service_id} - {self.date}"


class Trip(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='trips')
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='trips', null=True)
    service = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='trips', null=True)
    service_ref = models.CharField(max_length=255, blank=True, default='', db_index=True)
    trip_id = models.CharField(max_length=255, db_index=True)
    trip_headsign = models.CharField(max_length=255, blank=True, null=True)
    trip_short_name = models.CharField(max_length=255, blank=True, null=True)
    direction_id = models.PositiveIntegerField(null=True, blank=True)
    block_id = models.CharField(max_length=255, blank=True, null=True)
    shape_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    wheelchair_accessible = models.PositiveIntegerField(default=0)
    bikes_allowed = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.trip_id} ({self.route})"


class StopTime(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='stop_times')
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='stop_times')
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name='stop_times', null=True)
    arrival_time = models.CharField(max_length=8, blank=True, null=True, db_index=True)
    departure_time = models.CharField(max_length=8, blank=True, null=True)
    stop_sequence = models.PositiveIntegerField()
    pickup_type = models.PositiveIntegerField(default=0)
    drop_off_type = models.PositiveIntegerField(default=0)
    shape_dist_traveled = models.FloatField(null=True, blank=True)
    timepoint = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ['stop_sequence']
        indexes = [
            models.Index(fields=['trip', 'stop_sequence']),
        ]

    def __str__(self):
        return f"Stop {self.stop_id} at {self.arrival_time}"


class Shape(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='shapes')
    shape_id = models.CharField(max_length=255, db_index=True)
    shape_pt_lat = models.FloatField()
    shape_pt_lon = models.FloatField()
    shape_pt_sequence = models.PositiveIntegerField()
    shape_dist_traveled = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['shape_id', 'shape_pt_sequence']
        indexes = [
            models.Index(fields=['shape_id', 'shape_pt_sequence']),
        ]

    def __str__(self):
        return f"{self.shape_id} pt {self.shape_pt_sequence}"
