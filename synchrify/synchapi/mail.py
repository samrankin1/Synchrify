from django.core import mail
from django.urls import reverse
from django.conf import settings


def send_activation_mail(request, email, token):
	with mail.get_connection() as connection:
		mail.EmailMessage(
			subject='Please Activate Your Synchrify Account',
			body=request.build_absolute_uri('/')[:-1] + reverse('synchapi:activate', args=[token]),
			to=[email],
			bcc=[settings.DEFAULT_FROM_EMAIL],
			connection=connection
		).send()
