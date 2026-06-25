from django.contrib import admin
from .models import Feed, Agency, Route, Stop, Trip, StopTime, Shape, Calendar, CalendarDate

admin.site.register(Feed)
admin.site.register(Agency)
admin.site.register(Route)
admin.site.register(Stop)
admin.site.register(Trip)
admin.site.register(StopTime)
admin.site.register(Shape)
admin.site.register(Calendar)
admin.site.register(CalendarDate)
