install_prerequisites:
	sudo apt update
	sudo apt upgrade -y
	sudo apt-get install stress-ng -y
	sudo apt-get install python3-pip -y
	pip3 install psutil requests httpx kubernetes
	pip3 install \
		annotated-types==0.7.0 \
		anyio==4.6.2.post1 \
		blinker==1.4 \
		cachetools==5.5.0 \
		certifi==2024.8.30 \
		charset-normalizer==3.4.0 \
		click==8.1.7 \
		command-not-found==0.3 \
		cryptography==3.4.8 \
		dbus-python==1.2.18 \
		distro==1.7.0 \
		distro-info===1.1build1 \
		durationpy==0.9 \
		exceptiongroup==1.2.2 \
		fastapi==0.115.5 \
		google-auth==2.36.0 \
		h11==0.14.0 \
		httplib2==0.20.2 \
		idna==3.10 \
		importlib-metadata==4.6.4 \
		jeepney==0.7.1 \
		keyring==23.5.0 \
		kubernetes==31.0.0 \
		launchpadlib==1.10.16 \
		lazr.restfulclient==0.14.4 \
		lazr.uri==1.0.6 \
		more-itertools==8.10.0 \
		netifaces==0.11.0 \
		oauthlib==3.2.2 \
		psutil==6.1.0 \
		pyasn1==0.6.1 \
		pyasn1_modules==0.4.1 \
		pydantic==2.10.2 \
		pydantic_core==2.27.1 \
		PyGObject==3.42.1 \
		PyJWT==2.3.0 \
		pyparsing==2.4.7 \
		python-apt==2.4.0+ubuntu1 \
		python-dateutil==2.9.0.post0 \
		PyYAML==5.4.1 \
		requests==2.32.3 \
		requests-oauthlib==2.0.0 \
		rsa==4.9 \
		SecretStorage==3.3.1 \
		six==1.16.0 \
		sniffio==1.3.1 \
		ssh-import-id==5.11 \
		starlette==0.41.3 \
		typing_extensions==4.12.2 \
		ubuntu-advantage-tools==8001 \
		ufw==0.36.1 \
		urllib3==2.2.3 \
		uvicorn==0.32.1 \
		wadllib==1.3.6 \
		websocket-client==1.8.0 \
		zipp==1.0.0
