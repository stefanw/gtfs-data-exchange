import app.basic
import utils

class MainPage(app.basic.BasePublicPage):
    def get(self):
        recent_agencies = utils.get_recent_agencies()
        recent_messages = utils.get_recent_messages()
        agency_count = utils.get_agency_count()
        
        self.render('index.html', recent_messages=recent_messages,
                                  recent_agencies=recent_agencies,
                                  agency_count=agency_count)

class Agencies(app.basic.BasePublicPage):
    def get(self):
        agencies = utils.get_all_agencies()
        
        grouped = {}
        for agency in agencies:
            letter = agency.name[0].upper()
            if letter not in grouped:
                grouped[letter] = []
            grouped[letter].append(agency)
        
        grouped = grouped.items()
        grouped.sort()
        agency_count = utils.get_agency_count()
        
        self.render('agencies.html', agencies=agencies,
                                    grouped_agencies=grouped,
                                    agency_count=agency_count)

class AgenciesByLocation(app.basic.BasePublicPage):
    def get(self):
        agencies = utils.get_all_agencies()
        # data = [[agency.country_name, agency.state_name, agency.name, agency] for agency in agencies]
        # data.sort()
        # agencies = [x[-1] for x in data]
        agency_count = utils.get_agency_count()
        
        self.render('agencies_bylocation.html', agencies=agencies, agency_count=agency_count)

class AgenciesByLastUpdate(app.basic.BasePublicPage):
    def get(self):
        agencies = utils.get_all_agencies()
        data = [[agency.lastupdate, agency] for agency in agencies]
        data.sort(reverse=True)
        agencies = [x[-1] for x in data]
        agency_count = utils.get_agency_count()
        
        self.render('agencies_bylastupdate.html', agencies=agencies, agency_count=agency_count)

class AgenciesAsTable(Agencies):
    def get(self):
        agencies = utils.get_all_agencies()
        agency_count = utils.get_agency_count()
        
        self.render('agencies_astable.html', agencies=agencies, agency_count=agency_count)

