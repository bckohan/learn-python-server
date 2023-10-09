export class URLResolver {
	
	match(kwargs, args, expected) {
		if (Array.isArray(expected)) {
			return Object.keys(kwargs).length === expected.length && expected.every(value => kwargs.hasOwnProperty(value));
		} else if (expected) {
			return args.length === expected;
		} else {
			return Object.keys(kwargs).length === 0 && args.length === 0;
		}
	}
	
	reverse(qname, options={}, args=[], query={}) {
		const kwargs = ((options.kwargs || null) || options) || {};
		args = ((options.args || null) || args) || [];
		query = ((options.query || null) || query) || {};
		let url = this.urls;
		for (const ns of qname.split(':')) {
			if (ns && url) { url = url.hasOwnProperty(ns) ? url[ns] : null; }
		}
		if (url) {
			let pth = url(kwargs, args);
			if (typeof pth === "string") {
				if (Object.keys(query).length !== 0) {
					const params = new URLSearchParams();
					for (const [key, value] of Object.entries(query)) {
						if (value === null || value === '') continue;
						if (Array.isArray(value)) value.forEach(element => params.append(key, element));
						else params.append(key, value);
					}
					const qryStr = params.toString();
					if (qryStr) return `${pth.replace(/\/+$/, '')}?${qryStr}`;
				}
				return pth;
			}
		}
		throw new TypeError(`No reversal available for parameters at path: ${qname}`);
	}
	
	urls = {
		"redirect_latest_docs": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args)) { return "/"; }
		},
		"course_docs": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args, ['course'])) { return `/docs/${kwargs["course"]}`; }
		},
		"repository_docs": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args, ['repository'])) { return `/docs/${kwargs["repository"]}`; }
		},
		"register": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args, ['repository'])) { return `/register/${kwargs["repository"]}`; }
		},
		"authorize_tutor": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args)) { return "/api/authorize_tutor"; }
		},
		"engagements-list": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args)) { return "/api/engagements/"; }
			if (this.match(kwargs, args, ['format'])) { return `/api/engagements.${kwargs["format"]}`; }
		},
		"engagements-detail": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args, ['engagement_id'])) { return `/api/engagements/${kwargs["engagement_id"]}/`; }
			if (this.match(kwargs, args, ['engagement_id','format'])) { return `/api/engagements/${kwargs["engagement_id"]}.${kwargs["format"]}`; }
		},
		"logs-list": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args)) { return "/api/logs/"; }
			if (this.match(kwargs, args, ['format'])) { return `/api/logs.${kwargs["format"]}`; }
		},
		"logs-detail": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args, ['pk'])) { return `/api/logs/${kwargs["pk"]}/`; }
			if (this.match(kwargs, args, ['pk','format'])) { return `/api/logs/${kwargs["pk"]}.${kwargs["format"]}`; }
		},
		"api-root": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args)) { return "/api/"; }
			if (this.match(kwargs, args, ['format'])) { return `/api/.${kwargs["format"]}`; }
		},
		"timeline": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args)) { return "/api/timeline"; }
			if (this.match(kwargs, args, ['uri'])) { return `/api/timeline/${kwargs["uri"]}`; }
			if (this.match(kwargs, args, ['id'])) { return `/api/timeline/${kwargs["id"]}`; }
		},
		"modules": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args, ['uri'])) { return `/api/modules/${kwargs["uri"]}`; }
			if (this.match(kwargs, args, ['id'])) { return `/api/modules/${kwargs["id"]}`; }
		},
		"get_log": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args, ['log_name'])) { return `/media/log_uploads/${kwargs["log_name"]}`; }
		},
		"student_timeline": (kwargs={}, args=[]) => {
			if (this.match(kwargs, args, ['uri'])) { return `/timeline/${kwargs["uri"]}`; }
			if (this.match(kwargs, args, ['id'])) { return `/timeline/${kwargs["id"]}`; }
		},
	}
};
