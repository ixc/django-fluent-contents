from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, FieldError
from django.db import models
from django.db.models.base import ModelBase
from django.template.defaultfilters import truncatewords
from django.utils.encoding import smart_str
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from content_placeholders.managers import PlaceholderManager
import types


class Placeholder(models.Model):
    """
    A placeholder is displayed at a page, rendering custom content.
    """
    # The 'role' field is useful for migrations by a CMS,
    # e.g. moving from a 2-col layout to a 3-col layout.
    # Based on the role of a pageitem, meaningful conversions can be made.
    MAIN = 'm'
    SIDEBAR = 's'
    RELATED = 'r'
    ROLES = (
        (MAIN, _('Main content')),
        (SIDEBAR, _('Sidebar content')),
        (RELATED, _('Related content'))
    )

    slot = models.SlugField(_('Slot'), help_text=_("A short name to identify the placeholder in the template code"))
    role = models.CharField(_('Role'), max_length=1, choices=ROLES, default=MAIN, help_text=_("This defines where the object is used."))

    # Track relation to parent
    parent_type = models.ForeignKey(ContentType)
    parent_id = models.IntegerField(null=True)    # Need to allow Null, because Placeholder is created before parent is saved.
    parent = GenericForeignKey('parent_type', 'parent_id')

    title = models.CharField(_('Admin title'), max_length=255, blank=True)

    objects = PlaceholderManager()

    class Meta:
        app_label = 'content_placeholders'  # required for subfolder
        verbose_name = _("Placeholder")
        verbose_name_plural = _("Placeholders")
        unique_together = ('parent_type', 'parent_id', 'slot')

    def __unicode__(self):
        return self.title or self.slot


    def get_allowed_plugins(self):
        """
        Return the plugins which are supported in this placeholder.
        """
        from content_placeholders import extensions  # avoid circular import
        return extensions.plugin_pool.get_plugins()


class ContentItemMetaClass(ModelBase):
    """
    Metaclass for all plugin models.

    Set db_table if it has not been customized.
    """
    # Inspired by from Django-CMS, (c) , BSD licensed.

    def __new__(mcs, name, bases, attrs):
        new_class = super(ContentItemMetaClass, mcs).__new__(mcs, name, bases, attrs)
        db_table  = new_class._meta.db_table
        app_label = new_class._meta.app_label

        if db_table.startswith(app_label + '_') and name != 'ContentItem':
            model_name = db_table[len(app_label)+1:]
            new_class._meta.db_table = "contentitem_%s_%s" % (app_label, model_name)

        # Enforce good manners.
        # The name is often not visible, except for the delete page.
        if name != 'ContentItem' and not hasattr(new_class, '__unicode__'):
            raise FieldError("The {0} class should implement a __unicode__() function.".format(name))

        return new_class


class ContentItem(models.Model):
    """
    A ```ContentItem``` is a content part which is displayed at a ``Placeholder``.
    The item is rendered by a ``ContentPlugin``.
    """
    __metaclass__ = ContentItemMetaClass

    # Currently the model has a connection back to the plugin, because it makes a lot of things easier
    # for the internal framework. For example, rendering the item while having a model.
    # That allows the render() function to be at the plugin itself.
    # The value is set by register()
    _content_plugin = None

    # Note the validation settings defined here are not reflected automatically
    # in the admin interface because it uses a custom ModelForm to handle these fields.

    # Track relation to parent
    # This makes it much easier to use it as inline.
    parent_type = models.ForeignKey(ContentType)
    parent_id = models.IntegerField(null=True)    # Need to allow Null, because Placeholder is created before parent is saved.
    parent = GenericForeignKey('parent_type', 'parent_id')

    placeholder = models.ForeignKey(Placeholder, related_name='contentitems', null=True)
    placeholder_slot = models.CharField(_("Placeholder"), max_length=50)  # needed to link to new placeholders
    sort_order = models.IntegerField(default=1)


    @property
    def plugin(self):
        """
        Access the parent plugin which renders this model.
        """
        return self._content_plugin


    def __unicode__(self):
        return '<%s: #%d, placeholder=%s>' % (self.__class__.__name__, self.id or 0, self.placeholder)


    class Meta:
        app_label = 'content_placeholders'  # required for models subfolder
        ordering = ('placeholder', 'sort_order')
        verbose_name = _('Contentplugin base')
        verbose_name_plural = _('Contentplugin bases')
