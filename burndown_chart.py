import argparse
import datetime
from redminelib import Redmine
from redminelib.exceptions import ResourceAttrError
from plotly.offline import plot
import plotly.graph_objs as go

dt_format = '%Y-%m-%d'
team = 'y'
dt_today = datetime.datetime.today()
today = datetime.datetime(dt_today.year, dt_today.month, dt_today.day, 0, 0, 0, 0)

def get_sprint_info(sprint_number = None):
    global today
    # Init with first sprint due date
    due_date = datetime.datetime(2017, 9, 26, 23, 59, 59, 999999)
    sprint_count = 0
    while True:
            sprint_count += 1
            start_date = due_date + datetime.timedelta(minutes=1)
            due_date += datetime.timedelta(days=14)
            # Break if wanted sprint was not provided and today is in the sprint
            if sprint_number == None and due_date > today:
                break

            # Sprint number is provided, so adjust settings accordingly
            elif sprint_number == sprint_count:

                # sprint is in the past, set today as last day of the sprint
                if today > due_date:
                    today = due_date

                # sprint is in the future, set today as first day of  the sprint
                elif today < start_date:
                    today = start_date
                break
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
        uid="a7c235",
        xsrc="gohals:114:5be4af",
        ysrc="gohals:114:d49a4c",
        hoverlabel=dict(font=dict(size=20, color="white"))
    )
    layout = go.Layout(
        autosize=True,
        title="Sprint " + str(sprint_info['num']) + " - Burndown chart - " + team_name + " QSF team",
        xaxis=dict(
            title="Iteration Timeline (working days)",
            autorange=True,
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

    fig = go.Figure(data=[trace_ideal_burn, trace_current_burn], layout=layout)
    plot(fig)


def init_actual_remaining(sprint_info):
    actual_remaining = {}
    for str_date in get_sprint_date_interval(sprint_info):
        date = datetime.datetime.strptime(str_date, dt_format)
        if date <= today and date.weekday() < 5:
            actual_remaining[str_date] = {'value': 0, 'story_list': []}
    return actual_remaining


def is_open(issue):
    return issue.status.name != "Resolved" and issue.status.name != "Rejected"


def query_redmine(sprint_info, apikey = None):
    project_list = ['suseqa', 'openqav3', 'openqatests']
    str_start_date = sprint_info['start_date'].strftime(dt_format)
    str_due_date = (sprint_info['due_date'] + datetime.timedelta(days=1)).strftime(dt_format)
    str_due_date = sprint_info['due_date'].strftime(dt_format)
    date_interval = '><' + str_start_date + '|' + str_due_date
    rm = Redmine('https://progress.opensuse.org', key=apikey)
    issues = rm.issue.filter( project_ids=project_list,
                              status_id='*',
                              due_date=date_interval,
                              subject="~[" + team + "]" )
    print("Sprint start date: " + str(sprint_info['start_date']))
    print("Sprint end date:   " + str(sprint_info['due_date']))

    print("\n".join(map(str, issues)))
    # Exclude epics and sagas
    issues = [issue for issue in issues if ('[epic]' not in issue.subject and '[saga]' not in issue.subject)]
    # Exclude blocked
    issues = [issue for issue in issues if issue.status.name != "Blocked"]
    # Filter out issues resolved outside of the sprint

    issues = [issue for issue in issues if (is_open(issue) or
                sprint_info['start_date'] <= issue.closed_on <= sprint_info['due_date'])]
    return issues


def adjust_remaining(actual_remaining, total_story_points, sprint_info):
    remaining_story_points = total_story_points
    for str_date in actual_remaining:
        if actual_remaining[str_date]:
            remaining_story_points += actual_remaining[str_date]['value']
            actual_remaining[str_date]['value'] = remaining_story_points

    str_today_date = today.strftime(dt_format)
    if actual_remaining[str_today_date]['value'] == 0:
        actual_remaining[str_today_date]['value'] = actual_remaining[str_today_date]['value']

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
        # Print processed tickets
        print("[{0:2}] {1} -> {2}".format(num, story.subject, story_points))
        if not is_open(story):
            closed_on = datetime.datetime(story.closed_on.year, story.closed_on.month, story.closed_on.day, 0, 0, 0, 0)
            day_before_sprint_start = sprint_info['start_date'] - datetime.timedelta(days=1)
            if closed_on == day_before_sprint_start:  # if resolved the day before starting the sprint
                closed_on += datetime.timedelta(days=1)
            if closed_on.weekday() == 5:
                closed_on += datetime.timedelta(days=2)  # if resolved on Saturday, move to Monday
            elif closed_on.weekday() == 6:
                closed_on += datetime.timedelta(days=1)  # if resolved on Sunday, move to Monday
            actual_remaining[closed_on.strftime(dt_format)]['value'] -= story_points
            story_desc = "[" + str(story_points) + "] @" + (story.assigned_to.name if hasattr(story, 'assigned_to') else '') + ": " + story.subject
            actual_remaining[closed_on.strftime(dt_format)]['story_list'].append(story_desc)

    actual_remaining = adjust_remaining(actual_remaining, total_story_points, sprint_info)
    return actual_remaining, total_story_points


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sprint", help="Provide sprint number for which you want to see the burndown chart")
    parser.add_argument("--apikey", help="Provide redmine apkey to have access to all projects")
    args = parser.parse_args()
    # Pass sprint number if provided as an argument
    sprint_info = get_sprint_info(int(args.sprint)) if args.sprint else get_sprint_info()
    stories = query_redmine(sprint_info, args.apikey)
    actual_remaining, total_story_points = calculate_burn(stories, sprint_info)
    if total_story_points == 0:
        print("No story points assigned, not plotting burndown chart!")
        return
    plot_chart(sprint_info, total_story_points, actual_remaining)


if __name__ == "__main__":
    main()
