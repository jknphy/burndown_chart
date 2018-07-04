#!/usr/bin/python3

import datetime
from redminelib import Redmine
from redminelib.exceptions import ResourceAttrError
from plotly.offline import plot
import plotly.graph_objs as go

dt_format = '%Y-%m-%d'
team = 'y'


def get_current_sprint_info():
    sprint0_end = datetime.datetime(2017, 9, 26, 0, 0, 0, 0)
    dt_today = datetime.datetime.today()
    today = datetime.datetime(dt_today.year, dt_today.month, dt_today.day, 0, 0, 0, 0)

    due_date = sprint0_end
    sprint_count = 0
    while due_date < today:
            sprint_count += 1
            start_date = due_date + datetime.timedelta(days=1)
            due_date += datetime.timedelta(days=14)
    return {'num': sprint_count, 'start_date': start_date, 'due_date': due_date}


def get_sprint_date_interval(sprint_info):
    return [(sprint_info['start_date'] + datetime.timedelta(days=x)).strftime(dt_format) for x in [0, 1, 2, 5, 6, 7, 8, 9, 12, 13]]


def plot_chart(sprint_info, total_story_points, actual_remaining):
    team_name = "YaST" if team == "y" else "User space"
    date_list = get_sprint_date_interval(sprint_info)

    text_list = []
    for date in actual_remaining.keys():
        story_list = actual_remaining[date]['story_list']
        text_list.append('<br>'.join(story_list)) if len(story_list) else text_list.append(None)

    trace_ideal_burn = go.Scatter(
        x=date_list,
        y=[x / 9.0 for x in range(9*total_story_points, -1, -total_story_points)],
        name="Ideal stories remaining",
        textsrc="gohals:114:c99b6e",
        type="scatter",
        uid="2b2777",
        xsrc="gohals:114:5be4af",
        ysrc="gohals:114:c99b6e",
        hoverlabel=dict(font=dict(size=20))
                                  )
    trace_current_burn = go.Scatter(
        x=date_list,
        y=list(actual_remaining[date]['value'] for date in actual_remaining.keys()),
        hovertext=text_list,
        name="Actual stories remaining",
        textsrc="gohals:114:c99b6e",
        type="scatter",
        uid="a7c235",
        xsrc="gohals:114:5be4af",
        ysrc="gohals:114:d49a4c",
        hoverlabel=dict(font=dict(size=20, color="white"))
    )
    data = go.Data([trace_ideal_burn, trace_current_burn])
    layout = go.Layout(
        autosize=True,
        title="Sprint " + str(sprint_info['num']) + " - Burndown chart - " + team_name + " QSF team",
        xaxis=dict(
            title="Iteration Timeline (working days)",
            autorange=True,
            range=date_list,
            type="category",
            tickvals=date_list,
        ),
        yaxis=dict(
            title="Sum of Story Estimates (story points)",
            autorange=True,
            type="linear"
        ),
        font=dict(family='Courier New, monospace', size=18, color='#7f7f7f')
    )

    fig = go.Figure(data=data, layout=layout)
    plot(fig)


def init_actual_remaining(sprint_info):
    actual_remaining = {}
    for str_date in get_sprint_date_interval(sprint_info):
        date = datetime.datetime.strptime(str_date, dt_format)
        dt_today = datetime.datetime.today()
        today = datetime.datetime(dt_today.year, dt_today.month, dt_today.day, 0, 0, 0, 0)
        if date <= today and date.weekday() < 5:
            actual_remaining[str_date] = {'value': 0, 'story_list': []}
    return actual_remaining


def query_redmine(sprint_info):
    project_list = ['suseqa', 'openqav3', 'openqatests']
    str_start_date = sprint_info['start_date'].strftime(dt_format)
    str_due_date = sprint_info['due_date'].strftime(dt_format)
    date_interval = '><' + str_start_date + '|' + str_due_date
    rm = Redmine('https://progress.opensuse.org', key='dc97b2582634ac80ee3a1cc388c324d6ff413a44')
    return rm.issue.filter(project_ids=project_list, status_id='*', due_date=date_interval, subject="~[" + team + "]")


def adjust_remaining(actual_remaining, total_story_points, sprint_info):
    remaining_story_points = total_story_points
    for str_date in actual_remaining:
        if actual_remaining[str_date]:
            remaining_story_points += actual_remaining[str_date]['value']
            actual_remaining[str_date]['value'] = remaining_story_points

    str_today_date = datetime.datetime.today().strftime(dt_format)
    str_yesterday_date = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime(dt_format)
    if actual_remaining[str_today_date]['value'] == 0:
        dt_today = datetime.datetime.today()
        today = datetime.datetime(dt_today.year, dt_today.month, dt_today.day, 0, 0, 0, 0)
        if sprint_info['start_date'] == today:
            actual_remaining[str_today_date]['value'] = total_story_points
        else:
            actual_remaining[str_today_date]['value'] = actual_remaining[str_yesterday_date]['value']

    return actual_remaining


def calculate_burn(stories, sprint_info):
    total_story_points = 0
    actual_remaining = init_actual_remaining(sprint_info)
    for num, story in enumerate(stories, start=1):
        try:
            story_points = int(story.estimated_hours)
        except ResourceAttrError:
            story_points = 0
        total_story_points += story_points

        if story.status.name == "Resolved":
            closed_on = story.closed_on
            dt = datetime.datetime(closed_on.year, closed_on.month, closed_on.day, 0, 0, 0, 0)
            if dt.weekday() == 5:
                dt += datetime.timedelta(days=2)  # if resolved on Saturday, move to Monday
            elif dt.weekday() == 6:
                dt += datetime.timedelta(days=1)  # if resolved on Sunday, move to Monday
            actual_remaining[dt.strftime(dt_format)]['value'] -= story_points
            actual_remaining[dt.strftime(dt_format)]['story_list'].append("[" + str(story_points) + "] @" + story.assigned_to.name + ": " + story.subject)

        print("[{0:2}] {1} -> {2}".format(num, story.subject, story_points))
    actual_remaining = adjust_remaining(actual_remaining, total_story_points, sprint_info)
    return actual_remaining, total_story_points


def main():
    sprint_info = get_current_sprint_info()
    stories = query_redmine(sprint_info)
    actual_remaining, total_story_points = calculate_burn(stories, sprint_info)
    plot_chart(sprint_info, total_story_points, actual_remaining)


if __name__ == "__main__":
    main()
