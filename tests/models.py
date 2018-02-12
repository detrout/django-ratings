from django.conf import settings
from django.db import models

from djangoratings.fields import AnonymousRatingField, RatingField

settings.RATINGS_VOTES_PER_IP = 1

class RatingTestModel(models.Model):
    rating = AnonymousRatingField(range=2, can_change_vote=True)
    rating2 = RatingField(range=2, can_change_vote=False)

    def __unicode__(self):
        return unicode(self.pk)

