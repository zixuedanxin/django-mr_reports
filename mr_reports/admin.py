
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.forms import ModelForm, PasswordInput
from django.conf import settings

from encrypted_fields import EncryptedCharField
from models import DataConnection, Parameter, DataSet, Style, Report, ReportDataSet, \
    DataSetParameter

### Hack to insert icons #######################################################
# I want to show icons for each model in the admin, but I can't alter the admin 
# template because this is a resdistributable app and the end users could already have
# django admin customization.  This code simply sticks the icons into the context 
# response and marks them as safe to display HTML right before it's rendered.
def insert_icons(response):
    image_by_model = {'DataConnection':'server.png', 'Parameter':'quiz.png', 
        'DataSet':'view_text.png', 'Style':'kcoloredit.png', 'Report':'tablet.png'}
    my_app_context = [d for d in response.context_data['app_list'] if d.get('app_label','') == u'mr_reports']
    if my_app_context:
        for m in my_app_context[0]['models']:
            if m['object_name'] in image_by_model:
                m['name'] = mark_safe(("<img src='/static/images/%s' /> " % image_by_model[m['object_name']]) + unicode(m['name']))
    return response 

def index(self, *args, **kwargs):
    response = admin.site.__class__.index(self, *args, **kwargs)
    return insert_icons(response)
admin.site.index = index.__get__(admin.site, admin.site.__class__)

def app_index(self, *args, **kwargs):
    response = admin.site.__class__.app_index(self, *args, **kwargs)
    return insert_icons(response)
admin.site.app_index = app_index.__get__(admin.site, admin.site.__class__)

### End Hack ###################################################################

class BaseAdmin(admin.ModelAdmin):
    readonly_fields = ('created_datetime','updated_datetime','created_by','last_updated_by')
    def save_model(self, request, obj, form, change):
        if hasattr(obj, 'created_by') and not obj.id:
            obj.created_by = request.user
        if hasattr(obj, 'last_updated_by'):
            obj.last_updated_by = request.user
        obj.save()

class DataConnectionAdmin(BaseAdmin):
    formfield_overrides = {
        EncryptedCharField: {'widget': PasswordInput(render_value=True)},
    }

class ParameterAdmin(BaseAdmin):
    if not getattr(settings,'MR_REPORTS_ALLOW_NATIVE_PYTHON_CODE_EXEC_ON_SERVER',False):
        readonly_fields = ('python_create_default',)

class DataSetParameterInline(admin.TabularInline):
    model = DataSetParameter
    #fields = (edit_parameter_link,)
    extra = 0
    #def edit_parameter_link(self, instance):
    #    return 'test' #instance.parameter.edit_link()
    #edit_parameter_link.short_description = "Edit Parameter"

class DataSetAdmin(BaseAdmin):
    class Media:
        js = ('js/create_parameter_edit_links.js',)

    if not getattr(settings,'MR_REPORTS_ALLOW_NATIVE_PYTHON_CODE_EXEC_ON_SERVER',False):
        readonly_fields = ('python_post_processing',)
    inlines = [DataSetParameterInline]
    exclude=('parameters',)

class StyleAdmin(BaseAdmin):
    pass

class ReportDataSetInline(admin.TabularInline):
    model = ReportDataSet #Report.datasets.through
    #fields = ('dataset__name','dataset__edit_link')
    extra = 0

class ReportAdmin(BaseAdmin):
    class Media:
        js = ('js/create_dataset_edit_links.js',)
    list_display = BaseAdmin.list_display + ('view_report',)
    exclude=('datasets',)
    inlines = [ReportDataSetInline,]


admin.site.register(DataConnection,DataConnectionAdmin)
admin.site.register(Parameter,ParameterAdmin)
admin.site.register(DataSet,DataSetAdmin)
admin.site.register(Style,StyleAdmin)
admin.site.register(Report,ReportAdmin)

