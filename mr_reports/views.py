
import datetime
import csv
import subprocess

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template import RequestContext, loader
from django.http import HttpResponse
from django import forms
from django.forms.forms import Form
import django.forms.fields
from django.conf import settings

from models import Report, Parameter, DataSet


def index(request):
    """For now show a simple page listing all reports.  
    Later it could be customizable, different for users, respect permissions,
    etc."""
    all_reports = Report.objects.all()

    #Footer:
    footer_html = getattr(settings,'MR_REPORTS_FOOTER_HTML',
        "<p><em>Generated by <a href=''>Mr. Reports</a>.</em></p>")

    return render(request, 'mr_reports/report_listing.html', locals())

def build_parameter_form(report):
    """Dynamically build a form class to handle the report's parameters"""
    all_parameters = []
    for dataset in report.datasets.all():
        for p in dataset.parameters.all():
            all_parameters.append(p)
    
    if all_parameters:
        #remove duplicates whilst preserving order
        unique_parameters = []
        [unique_parameters.append(item) for item in all_parameters if item not in unique_parameters]
        
        #TODO: requested form order isn't always being respected, investigate

        class ParameterForm(Form):
            def __init__(self, *args, **kwargs):
                super(ParameterForm, self).__init__(*args, **kwargs)
                for i,p in enumerate(unique_parameters):
                    kwargs2 = {}
                    if p.label:
                        kwargs2['label'] = p.label.title()
                    else:
                        kwargs2['label'] = p.name.replace('_',' ').title()
                    if p.comment:
                        kwargs2['help_text'] = p.comment
                    if p.data_type == 'CharField':
                        kwargs2['max_length']=255
                    kwargs2['required']=p.required
                    default = p.create_default()
                    if default:
                        kwargs2['initial'] = default
                    #Specify special widgets
                    if p.data_type.lower() == 'datefield':
                        kwargs2['widget'] = forms.DateInput(attrs={'class':'date'}) #SelectDateWidget
                    elif p.data_type.lower() == 'datetimefield':
                        kwargs2['widget'] = forms.SplitDateTimeWidget(attrs={'class':'datetime'}) #forms.DateTimeInput
                    elif p.data_type.lower() == 'timefield':
                        kwargs2['widget'] = forms.TimeInput(attrs={'class':'time'})
                    self.fields[p.name] = getattr(django.forms.fields,p.data_type)(**kwargs2)
                    #preserse order of parameters in form display (possibly unnecessary)
                    self.fields[p.name].creation_counter = i
        return ParameterForm
    else:
        return None

def data_to_csv(response, datasets):
    w=csv.writer(response,dialect='excel')
    for i,(dataset,data,columns) in enumerate(datasets):
        if i>0:
            #a row of padding between data sets
            w.writerows([['' for col in columns]])
        w.writerows([[s.encode("utf-8") for s in columns]])
        w.writerows(data)
    return response

@login_required
def report(request, report_id, format=''):
    """Render a given report, or ask for parameters if needed"""
    report = get_object_or_404(Report, pk=report_id)

    today = datetime.datetime.today()

    curr_url = request.get_full_path()

    datasets = []

    #If form exists, and is not bound, or is not valid, prompt for parameters
    #otherwise render report
    
    ParameterForm = build_parameter_form(report)
    prompt_for_parameters = False
    if ParameterForm:
        if request.GET:
            parameter_form = ParameterForm(request.GET)
            if parameter_form.is_valid():
                #render report
                datasets = report.get_all_data(parameter_form)
                #Include links to PDF and CSV versions of report
                csv_url = ''.join([curr_url.split('?')[0],'csv/?',curr_url.split('?')[1]])
                pdf_url = ''.join([curr_url.split('?')[0],'pdf/?',curr_url.split('?')[1]])
            else:
                prompt_for_parameters = True
        else:
            prompt_for_parameters = True
            parameter_form = ParameterForm()
    else:
        #render report
        parameter_form = None
        datasets = report.get_all_data(parameter_form)
        #Include links to PDF and CSV versions of report
        csv_url = curr_url + 'csv/'
        pdf_url = curr_url + 'pdf/'

    #Footer:
    footer_html = getattr(settings,'MR_REPORTS_FOOTER_HTML',
        "<p><em>Generated by <a href=''>Mr. Reports</a>.</em></p>")

    #Handle alternative outputs
    if format=='csv':
        assert datasets and not prompt_for_parameters
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s.csv"' % report.filename()
        response = data_to_csv(response,datasets)
        return response
    elif format=='pdf':
        assert datasets and not prompt_for_parameters
        #Hit this same url with HTML-to-PDF tool and return PDF
        if not getattr(settings, 'MR_REPORTS_WKHTMLTOPDF_PATH',''):
            return HttpResponse("PDF generation not available. Please add and set 'MR_REPORTS_WKHTMLTOPDF_PATH' in your settings.py file.")
        #Render normal page HTML, and feed it 
        command = [getattr(settings, 'MR_REPORTS_WKHTMLTOPDF_PATH')]
        command += getattr(settings, 'MR_REPORTS_WKHTMLTOPDF_OPTIONS',[])
        command += ['--page-size', report.pdf_paper_size, '--orientation', report.pdf_orientation]
        command += ["-","-"] #"-" to tell WKHTMLTOPDF to use pipes for input and output
        #print ' '.join(command)
        wkhtml2pdf = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        template = loader.get_template('mr_reports/report.html')
        context = RequestContext(request, locals())
        html = template.render(context).encode('utf8')
        wkdata = wkhtml2pdf.communicate(html)
        pdf = wkdata[0];
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=%s.pdf' % report.filename()
        response.write(pdf)
        return response
    else:
        #normal page render
        return render(request, 'mr_reports/report.html', locals())

