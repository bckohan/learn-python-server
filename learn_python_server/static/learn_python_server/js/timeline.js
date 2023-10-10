import { URLResolver } from './urls.js';

function formatDateTime(date) {
  let hours = date.getHours();
  const minutes = date.getMinutes();
  const seconds = date.getSeconds();
  const ampm = hours >= 12 ? 'pm' : 'am';
  
  // Convert hour from 24-hour to 12-hour format
  hours = hours % 12;
  
  // 12 AM should be 12, not 0
  hours = hours ? hours : 12;

  // Pad minutes and seconds with leading zeros
  const formattedMinutes = String(minutes).padStart(2, '0');
  const formattedSeconds = String(seconds).padStart(2, '0');
  
  return `${hours}:${formattedMinutes}:${formattedSeconds} ${ampm}`;
}

function areSameDate(ts1, ts2) {
  const date1 = new Date(ts1);
  const date2 = new Date(ts2);

  return date1.getFullYear() === date2.getFullYear() &&
         date1.getMonth() === date2.getMonth() &&
         date1.getDate() === date2.getDate();
}

class TimelineEvent {

    children = [];
    timestamp = null;
    stop = null;
    toggle = false;
    show_log = false;
    level = 0;

    constructor(event) {
      this.event = event;
      this.timestamp = new Date(event.timestamp);
      if (event.hasOwnProperty('stop')) {
        this.stop = new Date(event.stop);
      }
    }
    
    contains(event) {
      if (this.stop == null) { return false; }
      if (event.hasOwnProperty('stop')) {
        if (this.stop < event.stop) {
          return false;
        }
      }
      return this.stop >= event.timestamp && this.timestamp <= event.timestamp;
    }

    getName() {
      return this.constructor.name;
    }

    render(parent) {
        let stop_html = '';
        if (this.stop != null) {
          stop_html = ` - <span class='stop'>${formatDateTime(this.stop)}</span>`;
        }
        let log_html = '';
        if (this.show_log && this.event.hasOwnProperty('log_link') && this.event.log_link != null) {
          log_html = `&nbsp;<a href="${this.event.log_link}" download><i class="fas fa-file-alt"></i></a>`;
        }
        let name_html = `<span><span class="event-name">${this.getName()}</span>${log_html}</span>`;
        if (this.toggle) {
          let togl = 'down';
          if (this.level >= 2) {
            togl = 'up';
          }
          name_html = `<div><button class="toggle-button"><i class="fas fa-chevron-${togl}"></i></button>${name_html}</div>`;
        }
        let div = $(`<div class="timeline-event ${this.css()}"><div class="event-header">${name_html}<span class="timing"><span class='start'>${formatDateTime(this.timestamp)}</span>${stop_html}</span></div></div>`);
        if (this.level >= 2) {
          div.addClass('collapsed');
        }
        parent.append(div);
        return div;
    }

    walk(parent) {
        let element = this.render(parent);
        this.children.forEach(child => child.walk(element));
    }

    css() {
      /* Converts ClassName to class-name */
      return this.constructor.name
        .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
        .toLowerCase();
    }

    insert(event) {
      event.level += 1;
      if (this.children.length > 0 && this.children[0].contains(event)) {
        this.children[0].insert(event);
      } else {
        this.children.unshift(event);
      }
    }
}

class DateContainer extends TimelineEvent {
  
  contains(event) {
    return areSameDate(this.timestamp, event.timestamp);
  }

  render(parent) {
    let div = $(`<div class="timeline-date"><span>${this.timestamp.toLocaleDateString()}</span></div>`);
    parent.append(div);
    let container = $('<div class="date-container"></div>');
    div.append(container);
    return div;
  }
}

class ToolRun extends TimelineEvent {

    num_tests = 0;
    assignments = {};
    toggle = true;
    show_log = true;

    getName() {
      return this.event.tool;
    }
    
    render(parent) {
      // if a tool run has no children, it's not interesting - don't render it
      if (this.children.length == 0) { return;}
      let div = super.render(parent);
      div.addClass(this.event.tool.toLowerCase());
      //div.prepend(`<div class="tool-name">${this.event.tool}</div>`);
      return div;
    }

    insert(event) {
      if (event instanceof TestEvent || event instanceof TutorSession) {
        let assignment = Timeline.assignments[event.event.assignment];
        if (assignment != null) {
          let assignment_ident = `${assignment.module.name}::${assignment.name}`;
          if (!this.assignments.hasOwnProperty(assignment_ident)) {this.assignments[assignment_ident] = assignment;}
        }
        if (event instanceof TestEvent) {this.num_tests++;}
      }
      super.insert(event);
    }
}

class TutorEngagement extends ToolRun {
  walk(parent) {
    let element = this.render(parent);
    // show the exchanges and tests in top-down
    this.children.reverse().forEach(child => child.walk(element));
  }
  getName() {
    return this.event.backend;
  }
}
class TutorExchange extends TimelineEvent {
    render(parent) {
        let div = super.render(parent);
        let container = $(`<div class="event-contents role-${this.event.role} collapsed"></div>`)
        div.append(container);
        container.append($(marked.parse(this.event.content)));
        return div;
    }
    getName() {
      return this.event.role;
    }
}

class TutorSession extends TimelineEvent {

    walk(parent) {
      let element = this.render(parent);
      // show the exchanges and tests in top-down
      this.children.reverse().forEach(child => child.walk(element));
    }
}

class LogEvent extends TimelineEvent {

    show_log = true;
    toggle = true;

    render(parent) {
        let div = super.render(parent);
        div.addClass(`level-${this.event.level.toLowerCase()}`);
        let container = $(`<div class="event-contents level-${this.event.level.toLowerCase()} collapsed"></div>`);
        div.append(container);
        let message = $('<pre></pre>');
        message.text(this.event.message);
        container.append(message);
        return div;
    }
}
class TestEvent extends LogEvent {
  render(parent) {
    let div = super.render(parent);
    div.addClass(`test-${this.event.result.toLowerCase()}`);
    return div;
  }
}

export class Timeline {

    timeline = [];
    data = [];

    static modules = {};
    static assignments = {};

    constructor(parent, repository, course) {
        this.parent = parent;
        this.repository = repository;
        this.course = course;
        this.urls = new URLResolver();

        $.ajax({
          url: this.urls.reverse('modules', {kwargs: {uri: this.course}, query: {format: 'json'}}),
          method: 'GET',
          success: (data) => {
            data.forEach(module => {
              if (!Timeline.modules.hasOwnProperty(module.id)) {
                Timeline.modules[module.id] = module;
              }
              module.assignments.forEach(assignment => {
                if (!Timeline.assignments.hasOwnProperty(assignment.id)) {
                  assignment.module = module;
                  Timeline.assignments[assignment.id] = assignment;
                }
              });
              delete module.assignments;
              Timeline.modules[module.id] = module;
            });
            this.build_timeline();
          },
          error: (error) => {
              alert(`Unable to fetch course assignments for ${this.course}`);
              console.log(error);
          }
        });
    }

    static create(event) {
        switch(event.resourcetype) {
            case 'ToolRun':
                return new ToolRun(event);
            case 'TutorEngagement':
                return new TutorEngagement(event);
            case 'TutorExchange':
                return new TutorExchange(event);
            case 'TutorSession':
                return new TutorSession(event);
            case 'LogEvent':
                return new LogEvent(event);
            case 'TestEvent':
                return new TestEvent(event);
            default:
                return new TimelineEvent(event);
        }
    }

    build_timeline() {
        $.ajax({
            url: this.urls.reverse('timeline', {kwargs: {uri: this.repository}, query: {format: 'json'}}),
            method: 'GET',
            success: (data) => {
                // we need to walk backwards to get parent/child relationships right
                // todo - smartly decide when you can break (on first-non-child) element
                // instead of rebuilding the whole list each time.
                this.parent.empty();
                this.timeline = [];
                this.data = this.data.concat(data.reverse());
                this.data.forEach(event => {
                    let event_obj = Timeline.create(event);
                    if (this.timeline.length > 0 && this.timeline[0].contains(event_obj)) {
                      this.timeline[0].insert(event_obj);
                    } else {
                      let date_container = new DateContainer(event_obj);
                      date_container.insert(event_obj)
                      this.timeline.unshift(date_container);
                    }
                });

                this.timeline.forEach(event => {
                  event.walk(this.parent);
                });
                $('.toggle-button').off('click');
                $('.toggle-button').on('click', function() {
                  $(this).find('i').toggleClass('fa-chevron-down fa-chevron-up');
                  let event = $(this).closest('.timeline-event');
                  event.find('.timeline-event').toggleClass('collapsed');
                  event.find('div.event-contents').toggleClass('collapsed');
                });
            },
            error: (error) => {
                console.log(error);
            }
        });
    }
}
