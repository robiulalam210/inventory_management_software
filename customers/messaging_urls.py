from django.urls import path

from . import messaging_views as v

urlpatterns = [
    path('schedules/', v.ScheduleListView.as_view(), name='message-schedules'),
    path('schedules/<int:pk>/', v.ScheduleDetailView.as_view(), name='message-schedule-detail'),
    path('schedules/<int:pk>/run/', v.ScheduleRunNowView.as_view(), name='message-schedule-run'),
    path('outbox/', v.OutboxListView.as_view(), name='message-outbox'),
    path('outbox/mark/', v.OutboxMarkView.as_view(), name='message-outbox-mark'),
    path('summary/', v.OutboxSummaryView.as_view(), name='message-summary'),
]
