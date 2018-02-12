from django.db.models import Manager
from django.db.models.query import QuerySet

from django.contrib.contenttypes.models import ContentType
import itertools
from collections import Counter

class VoteQuerySet(QuerySet):
    def delete(self, *args, **kwargs):
        """Handles updating the related `votes` and `score` fields attached to the model."""
        # XXX: circular import
        from fields import RatingField

        qs = self.distinct().values_list('content_type', 'object_id').order_by('content_type')
    
        to_update = []
        for content_type, objects in itertools.groupby(qs, key=lambda x: x[0]):
            model_class = ContentType.objects.get(pk=content_type).model_class()
            if model_class:
                to_update.extend(list(model_class.objects.filter(pk__in=list(objects)[0])))
        
        retval = super(VoteQuerySet, self).delete(*args, **kwargs)
        
        # TODO: this could be improved
        for obj in to_update:
            for field in getattr(obj, '_djangoratings', []):
                getattr(obj, field.name)._update(commit=False)
            obj.save()
        
        return retval
        
class VoteManager(Manager):
    def get_query_set(self):
        return VoteQuerySet(self.model)

    def get_for_user_in_bulk(self, objects, user):
        objects = list(objects)
        if len(objects) > 0:
            ctype = ContentType.objects.get_for_model(objects[0])
            votes = list(self.filter(content_type__pk=ctype.id,
                                     object_id__in=[obj._get_pk_val() \
                                                    for obj in objects],
                                     user__pk=user.id))
            vote_dict = dict([(vote.object_id, vote) for vote in votes])
        else:
            vote_dict = {}
        return vote_dict

class SimilarUserManager(Manager):
    def get_recommendations(self, user, model_class, min_score=1):
        from djangoratings.models import Vote, IgnoredObject
        
        content_type = ContentType.objects.get_for_model(model_class)
        
        params = dict(
            v=Vote._meta.db_table,
            sm=self.model._meta.db_table,
            m=model_class._meta.db_table,
            io=IgnoredObject._meta.db_table,
        )
        
        objects = model_class._default_manager.extra(
            tables=[params['v']],
            where=[
                '%(v)s.object_id = %(m)s.id and %(v)s.content_type_id = %%s' % params,
                '%(v)s.user_id IN (select to_user_id from %(sm)s where from_user_id = %%s and exclude = 0)' % params,
                '%(v)s.score >= %%s' % params,
                # Exclude already rated maps
                '%(v)s.object_id NOT IN (select object_id from %(v)s where content_type_id = %(v)s.content_type_id and user_id = %%s)' % params,
                # IgnoredObject exclusions
                '%(v)s.object_id NOT IN (select object_id from %(io)s where content_type_id = %(v)s.content_type_id and user_id = %%s)' % params,
            ],
            params=[content_type.id, user.id, min_score, user.id, user.id]
        ).distinct()

        # objects = model_class._default_manager.filter(pk__in=content_type.votes.extra(
        #     where=['user_id IN (select to_user_id from %s where from_user_id = %d and exclude = 0)' % (self.model._meta.db_table, user.pk)],
        # ).filter(score__gte=min_score).exclude(
        #     object_id__in=IgnoredObject.objects.filter(content_type=content_type, user=user).values_list('object_id', flat=True),
        # ).exclude(
        #     object_id__in=Vote.objects.filter(content_type=content_type, user=user).values_list('object_id', flat=True)
        # ).distinct().values_list('object_id', flat=True))
        
        return objects
    
    def update_recommendations(self):
        # TODO: this doesnt handle scores that have multiple values (e.g. 10 points, 5 stars)
        # due to it calling an agreement as score = score. We need to loop each rating instance
        # and express the condition based on the range.
        from djangoratings.models import Vote, SimilarUser
        from django.db import connection
        self.model.objects.get_queryset().delete()
        votes = Vote.objects.exclude(user_id=None).order_by('object_id', 'content_type_id', 'user_id')

        agreement = Counter()
        disagreement = Counter()

        vote_iter = votes.iterator()
        v = next(vote_iter)
        cur_object = v.object_id
        cur_content = v.content_type_id
        cur_user = v.user_id
        cur_score = v.score
        for v in vote_iter:
            if v.object_id == cur_object and v.content_type_id == cur_content:
                if v.user_id == cur_user:
                    pass
                else:
                    agreement[(cur_user, v.user_id)] += int(v.score == cur_score)
                    disagreement[(cur_user, v.user_id)] += int(v.score != cur_score)
            cur_object = v.object_id
            cur_content = v.content_type_id
            cur_user = v.user_id
            cur_score = v.score

        for from_user, to_user in agreement.keys():
            su = SimilarUser(
                from_user_id = from_user,
                to_user_id = to_user,
                agrees = agreement[(from_user, to_user)],
                disagrees = disagreement[(from_user, to_user)],
                exclude=0)
            su.save()
            su = SimilarUser(
                from_user_id = to_user,
                to_user_id = from_user,
                agrees = agreement[(to_user, from_user)],
                disagrees = disagreement[(to_user, from_user)],
                exclude=0)
            su.save()
