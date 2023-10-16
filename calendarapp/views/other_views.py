# cal/views.py

from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.views import generic
from django.utils.safestring import mark_safe
from datetime import timedelta, datetime, date
import calendar
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from itertools import chain
import pandas as pd
import os
from django.core.files.storage import FileSystemStorage


from calendarapp.models import EventMember, Event
from calendarapp.utils import Calendar
from calendarapp.forms import EventForm, AddMemberForm


def get_date(req_day):
    if req_day:
        year, month = (int(x) for x in req_day.split("-"))
        return date(year, month, day=1)
    return datetime.today()


def prev_month(d):
    first = d.replace(day=1)
    prev_month = first - timedelta(days=1)
    month = "month=" + str(prev_month.year) + "-" + str(prev_month.month)
    return month


def next_month(d):
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    last = d.replace(day=days_in_month)
    next_month = last + timedelta(days=1)
    month = "month=" + str(next_month.year) + "-" + str(next_month.month)
    return month


class CalendarView(LoginRequiredMixin, generic.ListView):
    login_url = "accounts:signin"
    model = Event
    template_name = "calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        d = get_date(self.request.GET.get("month", None))
        cal = Calendar(d.year, d.month)
        html_cal = cal.formatmonth(withyear=True)
        context["calendar"] = mark_safe(html_cal)
        context["prev_month"] = prev_month(d)
        context["next_month"] = next_month(d)
        return context


@login_required(login_url="signup")
def create_event(request):
    form = EventForm(request.POST or None)
    if request.POST and form.is_valid():
        title = form.cleaned_data["title"]
        description = form.cleaned_data["description"]
        start_time = form.cleaned_data["start_time"]
        end_time = form.cleaned_data["end_time"]
        Event.objects.get_or_create(
            user=request.user,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
        )
        return HttpResponseRedirect(reverse("calendarapp:calendar"))
    return render(request, "event.html", {"form": form})


class EventEdit(generic.UpdateView):
    model = Event
    fields = ["title", "description", "start_time", "end_time"]
    template_name = "calendar.html"


class EventDelete(generic.DeleteView):
    model = Event
    success_url = reverse_lazy("calendarapp:calendar")
    template_name = "calendar.html"

@login_required(login_url="signup")
def event_details(request, event_id):
    event = Event.objects.get(id=event_id)
    eventmember = EventMember.objects.filter(event=event)
    context = {"event": event, "eventmember": eventmember}
    return render(request, "event-details.html", context)


def add_eventmember(request, event_id):
    forms = AddMemberForm()
    event = Event.objects.get(id=event_id)
    eventmember = EventMember.objects.filter(event=event)
    if request.method == "POST":
        forms = AddMemberForm(request.POST)
        if forms.is_valid():
            member = EventMember.objects.filter(event=event_id)
            if member.count() <= 9:
                user = forms.cleaned_data["user"]
                EventMember.objects.create(event=event, user=user)
                return redirect("calendarapp:calendar")
            else:
                print("--------------User limit exceed!-----------------")
    context = {"form": forms, "event":event, "eventmember": eventmember}
    return render(request, "add_member.html", context)

@login_required(login_url="signup")
def search(request):
    events = Event.objects.get_all_events(user=request.user)
    events_filter = []
    if request.method == 'POST':
        from_date = request.POST['fromDate']
        to_date = request.POST['toDate']
        from_date_object = datetime.strptime(from_date, '%Y-%m-%dT%H:%M')
        to_date_object = datetime.strptime(to_date, '%Y-%m-%dT%H:%M')
        for event in events:
            if event.start_time >= from_date_object and event.start_time <= to_date_object:
                events_filter.append(event)
    return render(request, "search.html", {'events_filter':events_filter})

@login_required(login_url="signup")
def searchTitle(request):
    events = Event.objects.get_all_events(user=request.user)
    events_filter = []
    if request.method == 'POST':
        title = request.POST['title']
        events_filter = Event.objects.filter(title__contains=title)
        print(title)
    return render(request, "search.html", {'events_filter':events_filter})

@login_required(login_url="signup")
def importExcel(request):
    events_import = []
    events = Event.objects.get_all_events(user=request.user)
    if request.method == 'POST':
        myfile = request.FILES.get('myfile')
        empexceldata = pd.read_excel(myfile)
        for i in range(len(empexceldata.index)):
            new_event = Event.objects.get_or_create(
                user = request.user,
                title = str(empexceldata["title"][i]),
                description = empexceldata["description"][i],
                start_time = empexceldata["start_time"][i],
                end_time = empexceldata["end_time"][i],
            )
            events_import.append(new_event)
    return render(request, "importExcel.html", {'events_import':events_import})

class EventMemberDeleteView(generic.DeleteView):
    model = EventMember
    template_name = "add_member.html"
    success_url = reverse_lazy("calendarapp:calendar")


class CalendarViewNew(LoginRequiredMixin, generic.View):
    login_url = "accounts:signin"
    template_name = "calendarapp/calendar.html"
    form_class = EventForm

    def get(self, request, *args, **kwargs):
        forms = self.form_class()
        events = Event.objects.get_all_events(user=request.user)
        events_month = Event.objects.get_running_events(user=request.user)
        events_member = EventMember.objects.filter(user=request.user)
        event_list = []
        for event_member in events_member:
            event_list.append({
                "id": event_member.event.id,
                "title": event_member.event.title,
                "description": event_member.event.description,
                "start": event_member.event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "end": event_member.event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
        # start: '2020-09-16T16:00:00'
        for event in events:
            event_list.append(
                {
                    "id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "start": event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end": event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),

                }
            )
        context = {"form": forms, "events": event_list,
                   "events_month": events_month,
                   "events_member": events_member}
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        forms = self.form_class(request.POST)
        if forms.is_valid():
            form = forms.save(commit=False)
            form.user = request.user
            form.save()
            return redirect("calendarapp:calendar")
        context = {"form": forms}
        return render(request, self.template_name, context)
