export 
/**
 * A url resolver class that provides an interface very similar to 
 * Django's reverse() function. This interface is nearly identical to 
 * reverse() with a few caveats:
 *
 *  - Python type coercion is not available, so care should be taken to
 *      pass in argument inputs that are in the expect string format.
 *  - Not all reversal behavior can be replicated but these are corner 
 *      cases that are not likely to be correct url specification to 
 *      begin with.
 *  - The reverse function also supports a query option to include url
 *      query parameters in the reversed url.
 *
 * @class
 */
class URLResolver {
	
	
	/**
	 * Instantiate this url resolver.
	 *
	 * @param {Object} options - The options object.
	 * @param {string} options.namespace - When provided, namespace will
	 *     prefix all reversed paths with the given namespace.
	 */
	constructor(options=null) {
		this.options = options || {};
		if (this.options.hasOwnProperty("namespace")) {
			this.namespace = this.options.namespace;
			if (!this.namespace.endsWith(":")) {
				this.namespace += ":";
			}
		} else {
			this.namespace = "";
		}
	}
	
	
	/**
	 * Given a set of args and kwargs and an expected set of arguments and
	 * a default mapping, return True if the inputs work for the given set.
	 *
	 * @param {Object} kwargs - The object holding the reversal named 
	 *     arguments.
	 * @param {string[]} args - The array holding the positional reversal 
	 *     arguments.
	 * @param {string[]} expected - An array of expected arguments.
	 * @param {Object.<string, string>} defaults - An object mapping 
	 *     default arguments to their values.
	 */
	#match(kwargs, args, expected, defaults={}) {
		if (defaults) {
			kwargs = Object.assign({}, kwargs);
			for (const [key, val] of Object.entries(defaults)) {
				if (kwargs.hasOwnProperty(key)) {
					if (kwargs[key] !== val && JSON.stringify(kwargs[key]) !== JSON.stringify(val) && !expected.includes(key)) { return false; }
					if (!expected.includes(key)) { delete kwargs[key]; }
				}
			}
		}
		if (Array.isArray(expected)) {
			return Object.keys(kwargs).length === expected.length && expected.every(value => kwargs.hasOwnProperty(value));
		} else if (expected) {
			return args.length === expected;
		} else {
			return Object.keys(kwargs).length === 0 && args.length === 0;
		}
	}
	
	
	/**
	 * Reverse a Django url. This method is nearly identical to Django's
	 * reverse function, with an additional option for URL parameters. See
	 * the class docstring for caveats.
	 *
	 * @param {string} qname - The name of the url to reverse. Namespaces
	 *   are supported using `:` as a delimiter as with Django's reverse.
	 * @param {Object} options - The options object.
	 * @param {string} options.kwargs - The object holding the reversal 
	 *   named arguments.
	 * @param {string[]} options.args - The array holding the reversal 
	 *   positional arguments.
	 * @param {Object.<string, string|string[]>} options.query - URL query
	 *   parameters to add to the end of the reversed url.
	 */
	reverse(qname, options={}) {
		if (this.namespace) {
			qname = `${this.namespace}${qname.replace(this.namespace, "")}`;
		}
		const kwargs = options.kwargs || {};
		const args = options.args || [];
		const query = options.query || {};
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
		"student_timeline": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["id"])) { return `/timeline/${kwargs["id"]}`; }
			if (this.#match(kwargs, args, ["uri"])) { return `/timeline/${kwargs["uri"]}`; }
		},
		"get_log": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["log_name"])) { return `/media/log_uploads/${kwargs["log_name"]}`; }
		},
		"modules": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["id"])) { return `/api/modules/${kwargs["id"]}`; }
			if (this.#match(kwargs, args, ["uri"])) { return `/api/modules/${kwargs["uri"]}`; }
		},
		"timeline": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["id"])) { return `/api/timeline/${kwargs["id"]}`; }
			if (this.#match(kwargs, args, ["uri"])) { return `/api/timeline/${kwargs["uri"]}`; }
			if (this.#match(kwargs, args)) { return "/api/timeline"; }
		},
		"api-root": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["format"])) { return `/api/.${kwargs["format"]}`; }
			if (this.#match(kwargs, args)) { return "/api/"; }
		},
		"logs-detail": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["pk","format"])) { return `/api/logs/${kwargs["pk"]}.${kwargs["format"]}`; }
			if (this.#match(kwargs, args, ["pk"])) { return `/api/logs/${kwargs["pk"]}/`; }
		},
		"logs-list": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["format"])) { return `/api/logs.${kwargs["format"]}`; }
			if (this.#match(kwargs, args)) { return "/api/logs/"; }
		},
		"engagements-detail": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["engagement_id","format"])) { return `/api/engagements/${kwargs["engagement_id"]}.${kwargs["format"]}`; }
			if (this.#match(kwargs, args, ["engagement_id"])) { return `/api/engagements/${kwargs["engagement_id"]}/`; }
		},
		"engagements-list": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["format"])) { return `/api/engagements.${kwargs["format"]}`; }
			if (this.#match(kwargs, args)) { return "/api/engagements/"; }
		},
		"authorize_tutor": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args)) { return "/api/authorize_tutor"; }
		},
		"register": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["repository"])) { return `/register/${kwargs["repository"]}`; }
		},
		"repository_docs": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["repository"])) { return `/docs/${kwargs["repository"]}`; }
		},
		"course_docs": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["course"])) { return `/docs/${kwargs["course"]}`; }
		},
		"redirect_latest_docs": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args)) { return "/"; }
		},
	}
};
