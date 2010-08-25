#!/usr/bin/env python

import wsgiref.handlers
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.api import mail

import webapp as webapp2
import model
import datetime
import logging
import utils
from django.core.paginator import ObjectPaginator

# app imports
import app.basic
import app.crawler
import app.upload
import app.admin
import app.api

class StaticPage(app.basic.BasePublicPage):
    def get(self):
        self.render('views/'+ self.request.uri.split('/')[-1] + '.html')

class SubmitFeedPage(StaticPage):
    # get will work automagically
    def post(self):
        ## send an email; render "thank you"
        
        feed_location = self.request.POST.get('feed_location')
        if not feed_location:
            return self.render('views/generic.html', {'error':'Feed Location is required'})
        
        agency_name = self.request.POST.get('agency_name')
        agency_location = self.request.POST.get('agency_location')
        contact_info = self.request.POST.get('contact_info')
        if users.get_current_user():
            user = users.get_current_user().email()
        else:
            user = ''
        
        if not user and not agency_name and not agency_location and not contact_info:
            return self.render('views/generic.html', {'error':'Agency Name required'})
        
        mail.send_mail(sender="Jehiah Czebotar <jehiah@gmail.com>",
                      to="Jehiah Czebotar <jehiah@gmail.com>",
                      subject="New GTFS Feed - %s" % (agency_name or feed_location),
                      body="""
Feed URL: %(feed_location)s
Agency Name: %(agency_name)s
Agency Location: %(agency_location)s
Point of Contact: %(contact_info)s
Logged In User: %(user)s
        """ % {
        'agency_name' : agency_name,
        'agency_location' : agency_location,
        'contact_info' : contact_info,
        'feed_location' : feed_location,
        'user' : user
        })
        
        self.render('views/generic.html', {'message':'Thank You For Your Submission'})


class RedirectAgencyList(app.basic.BasePublicPage):
    def get(self):
        self.redirect('/agencies')




class Agencies(app.basic.BasePublicPage):
    def get(self):
        agencies = utils.getAllAgencies()
        
        grouped = {}
        for agency in agencies:
            letter = agency.name[0].upper()
            if letter not in grouped:
                grouped[letter] = []
            grouped[letter].append(agency)
        
        grouped = grouped.items()
        grouped.sort()
        agency_count = utils.getAgencyCount()
        
        self.render('views/agencies.html', {'agencies':agencies, 'grouped_agencies':grouped, 'agency_count':agency_count})

class AgenciesByLocation(app.basic.BasePublicPage):
    def get(self):
        agencies = utils.getAllAgencies()
        data = [[agency.country_name, agency.state_name, agency.name, agency] for agency in agencies]
        data.sort()
        agencies = [x[-1] for x in data]
        agency_count = utils.getAgencyCount()
        
        self.render('views/agencies_bylocation.html', {'agencies':agencies, 'agency_count':agency_count})

class AgenciesByLastUpdate(app.basic.BasePublicPage):
    def get(self):
        agencies = utils.getAllAgencies()
        data = [[agency.lastupdate, agency] for agency in agencies]
        data.sort(reverse=True)
        agencies = [x[-1] for x in data]
        agency_count = utils.getAgencyCount()
        
        self.render('views/agencies_bylastupdate.html', {'agencies':agencies, 'agency_count':agency_count})

class AgenciesAsTable(Agencies):
    def get(self):
        agencies = utils.getAllAgencies()
        agency_count = utils.getAgencyCount()
        
        self.render('views/agencies_astable.html', {'agencies':agencies, 'agency_count':agency_count})

class MainPage(app.basic.BasePublicPage):
    def get(self):
        recentAgencies = utils.getRecentAgencies()
        recentMessages = utils.getRecentMessages()
        self.render('views/index.html', {'recentMessages':recentMessages,
                                        'recentAgencies':recentAgencies})

class CommentPage(app.basic.BasePublicPage):
    def get(self, key=None):
        if not key:
            return self.error(404)
        if not key.isdigit():
            try:
                obj = db.get(db.Key(key))
                return self.redirect('/meta/%d' % obj.key().id())
            except:
                logging.exception('key not found %s' % key)
                return self.error(404)
        
        try:
            obj = model.Message.get_by_id(int(key))
            # obj = db.get(db.Key(key))
        except:
            logging.exception('key not found %s' % key)
            return self.error(404)
        if not obj:
            return self.error(404)
        self.render('views/comment.html', {'msg':obj})

class CommentAdminPage(app.basic.BasePublicPage):
    @app.basic.admin_required
    def get(self, key=None):
        if not key:
            return self.error(404)
        try:
            obj = db.get(db.Key(key))
        except:
            return self.error(404)
        if not obj:
            return self.error(404)
        self.render('views/comment_admin.html', {'msg':obj})
    @app.basic.admin_required
    def post(self, key=None):
        try:
            obj = db.get(db.Key(key))
        except:
            return self.error(404)
        obj.content = self.request.POST.get('comments', obj.content)
        obj.put()
        self.redirect('/meta/%d' % obj.key().id())


class QueuePage(app.basic.BasePublicPage):
    #@app.basic.login_required
    def get(self):
        if not self.request.GET.get('key', '') or not self.request.GET.get('bucket', '').startswith('gtfs'):
            return self.redirect('/upload')
        self.render('views/queue.html')


class FeedPage(app.basic.BasePublicPage):
    def get(self, userOrAgency=None, id=None):
        context = {'userOrAgency':userOrAgency, 'u':id, 'id':id}
        self.response.headers['Content-Type'] = 'application/atom+xml'
        if not userOrAgency:
            context['messages'] = model.Message.all().filter('date >', datetime.datetime.now()-datetime.timedelta(30)).order('-date').fetch(25)
            self.render('views/atom.xml', context)
        elif userOrAgency == 'user':
            import urllib
            user = urllib.unquote(id)
            if '@' in user:
                u = users.User(user)
            else:
                u = users.User(user+'@gmail.com')
            context['messages'] = model.Message.all().filter('date >', datetime.datetime.now()-datetime.timedelta(30)).filter('user =', u).order('-date').fetch(25)
            self.render('views/agency_atom.xml', context)
        elif userOrAgency == 'agency':
            s = utils.lookupAgencyAlias(id)
            if s:
                return self.redirect('/%s/%s/feed' % (userOrAgency, s))
            
            agency = model.Agency.all().filter('slug =', id).get()
            context['agency'] = agency
            context['messages'] = [x.message for x in model.MessageAgency.all().filter('agency =', agency).filter('date >', datetime.datetime.now()-datetime.timedelta(30)).order('-date').fetch(25)]
            self.render('views/agency_atom.xml', context)

class UserPage(app.basic.BasePublicPage):
    def get(self, user):
        import urllib
        user = urllib.unquote(user)
        if '@' in user:
            u = users.User(user)
        else:
            u = users.User(user+'@gmail.com')
        messages= model.Message.all().filter('user =', u).order('-date').fetch(1000)
        
        if not messages and not users.get_current_user():
            return self.error(404)
        if not messages and users.get_current_user().email() != u.email():
            return self.error(404)
        
        paginator = ObjectPaginator(messages, 15, 1)
        try:
            page = int(self.request.GET.get('page', '1'))
        except ValueError:
            page = 1
        
        try:
            records = paginator.get_page(page-1)
        except:
            records = paginator.get_page(0)
            page = 1
        self.render('views/user.html', {'u':u, 'messages':records, 'paginator':paginator,
        "next" : paginator.has_next_page(page-1), 'previous':paginator.has_previous_page(page-1), 'previous_page_number':page-1, 'next_page_number':page+1, "page" : page})

class LatestAgencyFile(app.basic.BasePublicPage):
    def get(self, slug):
        s = utils.lookupAgencyAlias(slug)
        if s:
            return self.redirect('/agency/%s/' % (s))
        agency = utils.getAgency(slug)
        if not agency:
            return self.error(404)
        message =model.MessageAgency.all().filter('agency', agency).order('-date').fetch(1)
        if message:
            return self.redirect(message[0].message.filelink())
        return self.error(404)
        
    

class AgencyPage(app.basic.BasePublicPage):
    def get(self, slug):
        s = utils.lookupAgencyAlias(slug)
        if s:
            return self.redirect('/agency/%s/' % (s))
        
        agency = utils.getAgency(slug)
        if not agency:
            return self.error(404)
        messages =model.MessageAgency.all().filter('agency', agency).order('-date').fetch(1000)
        self.render('views/agency.html', {'agency':agency, 'messages':messages})
    
    @app.basic.login_required
    def post(self, slug):
        key = 'Agency.slug.%s' % slug
        agency = memcache.get(key)
        if not agency:
            agency = model.Agency.all().filter('slug =', slug).get()
            if not agency:
                return self.error(404)
            memcache.set(key, agency)
        if not self.request.POST.get('comments', ''):
            self.redirect(agency.link())
        m = model.Message(user=users.get_current_user(), content=self.request.POST.get('comments', ''))
        m.put()
        ma = model.MessageAgency()
        ma.message = m
        ma.hasFile = False
        ma.agency = agency
        ma.put()
        memcache.delete('Message.recent')
        self.redirect(agency.link())

class AgencyEditPage(app.basic.BasePublicPage):
    @app.basic.admin_required
    def get(self, slug):
        s = utils.lookupAgencyAlias(slug)
        if s:
            return self.redirect('/agency/%s/edit' % (s))
        
        key = 'Agency.slug.%s' % slug
        agency = memcache.get(key)
        if not agency:
            agency = model.Agency.all().filter('slug =', slug).get()
            if not agency:
                return self.error(404)
            memcache.set(key, agency)
        
        self.render('views/agency_edit.html', {'agency':agency})
    
    @app.basic.login_required
    def post(self, slug):
        key = 'Agency.slug.%s' % slug
        agency = memcache.get(key)
        if not agency:
            agency = model.Agency.all().filter('slug =', slug).get()
            if not agency:
                return self.error(404)
        
        # agency.name = self.request.POST.get('name', agency.name)
        # agency.slug = self.request.POST.get('slug', agency.slug)
        agency.description = self.request.POST.get('description', agency.description)
        agency.url = self.request.POST.get('url', agency.url)
        
        agency.country_name = self.request.POST.get('country', agency.country_name).strip()
        agency.state_name = self.request.POST.get('state', agency.state_name).strip()
        agency.area_name = self.request.POST.get('area', agency.area_name).strip()
        agency.feed_baseurl = self.request.POST.get('feed', agency.feed_baseurl).strip()
        agency.license_url = self.request.POST.get('license', agency.license_url).strip()
        agency.is_official = self.request.POST.get('official', '0') == '1'
        
        # agency.lastupdate = datetime.datetime.now() # this is for the last message 'update'
        agency.put()
        memcache.delete(key)
        #memcache.delete('Agency.recent')
        memcache.delete('Agency.all')
        memcache.set('Agency.slug.%s' % agency.slug, agency)
        
        self.render('views/generic.html', {'message':'Agency %s updated' % agency.name})


class ZipFilePage(app.basic.BasePublicPage):
    def __before__(self, *args):
        pass
    
    def get(self, name):
        key = 'DataFile.name.%s' % name
        f = memcache.get(key)
        if not f:
            f = model.Message.all().filter('filename =', name).get()
            memcache.set(key, f)
        production = self.request.url.find('www.gtfs-data-exchange.com')!= -1
        
        if f:
            return self.redirect(f.filelink(production=production))
        else:
            return self.error(404)



def real_main():
    application = webapp2.WSGIApplication2(
                  [
                  #('/sitemap.xml', Sitemap),
                   ('/', MainPage),
                   ('/how-to-provide-open-data', StaticPage),
                   ('/submit-feed', SubmitFeedPage),
                   ('/upload', app.upload.UploadFile),
                   ('/queue', QueuePage),
                   ('/feed', FeedPage),
                   ('/meta/(?P<key>.*?)/edit/?', CommentAdminPage),
                   ('/meta/(?P<key>.*?)/?', CommentPage),
                   ('/(?P<userOrAgency>user)/(?P<id>.*?)/feed/?', FeedPage),
                   ('/user/(?P<user>.*?)/?', UserPage),
                   ('/(?P<userOrAgency>agency)/(?P<id>.*?)/feed/?', FeedPage),
                   ('/agency/', RedirectAgencyList),
                   ('/agencies/bylocation', AgenciesByLocation),
                   ('/agencies/bylastupdate', AgenciesByLastUpdate),
                   ('/agencies/astable', AgenciesAsTable),
                   ('/agencies', Agencies),
                   ('/agency/(?P<slug>.*?).json$', app.api.APIAgencyPage),
                   ('/agency/(?P<slug>.*?)/latest.zip', LatestAgencyFile),
                   ('/agency/(?P<slug>.*?)/edit', AgencyEditPage),
                   ('/agency/(?P<slug>.*?)/?', AgencyPage),
                   ('/gtfs/(?P<name>.*\.zip)', ZipFilePage),
                   
                   ('/a/', app.admin.AdminIndex),
                   ('/a/aliases', app.admin.AdminAliases),
                   
                   ('/a/crawler', app.crawler.CrawlerMain),
                   ('/crawl/nexturl', app.crawler.CrawlNextUrl),
                   ('/crawl/headers', app.crawler.CrawlHeaders),
                   ('/crawl/shouldSkip', app.crawler.CrawlShouldSkip),
                   ('/crawl/upload', app.crawler.CrawlUpload),
                   ('/crawl/undoLastRun', app.crawler.CrawlUndoLastRun),
                   
                   (r'^/api/agency$', app.api.APIAgencyPage),
                   (r'^/api/agencies$', app.api.APIAgencies),
                   ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)

def profile_main():
    # This is the main function for profiling
    # We've renamed our original main() above to real_main()
    import cProfile, pstats
    prof = cProfile.Profile()
    prof = prof.runctx("real_main()", globals(), locals())
    print "<pre>"
    stats = pstats.Stats(prof)
    stats.sort_stats("time")  # Or cumulative
    stats.print_stats(120)  # 80 = how many to print
    # The rest is optional.
    # stats.print_callees()
    # stats.print_callers()
    print "</pre>"

#main = profile_main
main = real_main
template.register_template_library('common.templatefilters')

if __name__ == '__main__':
    # logging.getLogger().setLevel(logging.info)
    main()


