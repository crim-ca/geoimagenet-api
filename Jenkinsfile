#!/usr/bin/env groovy

pipeline {
    agent any

    environment {
        TAG_NAME = sh(returnStdout: true, script: '[[ -z $(git tag -l --points-at HEAD) ]] && printf latest || printf $(git tag -l --points-at HEAD)')
        LOCAL_IMAGE_NAME = "geoimagenet_api:$TAG_NAME"
        LATEST_IMAGE_NAME = "docker-registry.crim.ca/geoimagenet/api:latest"
        TAGGED_IMAGE_NAME = "docker-registry.crim.ca/geoimagenet/api:$TAG_NAME"
        TEST_OUTPUT = "test_output"
    }

    options {
        buildDiscarder (logRotator(numToKeepStr:'10'))
    }

    stages {

        stage('Build') {
            steps {
                sh 'rm -rf ${TEST_OUTPUT}'
                sh 'env | sort'
                sh 'docker build -t $LOCAL_IMAGE_NAME .'
            }
        }

        stage('Test') {
            steps {
                sh 'mkdir ${TEST_OUTPUT}'
                script {
                    docker.image('kartoza/postgis:9.6-2.4').withRun('-e "ALLOW_IP_RANGE=0.0.0.0/0" -e "IP_LIST=*" -e "POSTGRES_USER=docker" -e "POSTGRES_PASS=docker"') { c ->
                        sh """
                        docker run --rm --link ${c.id}:postgis -v \$(pwd)/${TEST_OUTPUT}:/code/${TEST_OUTPUT} -e GEOIMAGENET_API_POSTGIS_USER=docker -e GEOIMAGENET_API_POSTGIS_PASSWORD=docker -e GEOIMAGENET_API_POSTGIS_HOST=postgis $LOCAL_IMAGE_NAME /bin/sh -c \" \
                        pip install -r requirements_dev.txt && \
                        pytest --junitxml ${TEST_OUTPUT}/junit.xml --cov 2>&1 | tee ${TEST_OUTPUT}/coverage.out && \
                        chmod -R 777 ${TEST_OUTPUT}\"
                        """
                    }
                }
            }
        }

        stage('Deploy') {
            when {
                environment name: 'GIT_LOCAL_BRANCH', value: 'release'
            }
            steps {
                sh 'docker tag $LOCAL_IMAGE_NAME $TAGGED_IMAGE_NAME'
                sh 'docker push $TAGGED_IMAGE_NAME'
                sh 'docker tag $LOCAL_IMAGE_NAME $LATEST_IMAGE_NAME'
                sh 'docker push $LATEST_IMAGE_NAME'
                sh 'ssh ubuntu@geoimagenetdev.crim.ca "cd ~/compose && ./geoimagenet-compose.sh pull api && ./geoimagenet-compose.sh up --force-recreate -d api"'
                slackSend channel: '#geoimagenet-dev', color: 'good', message: "*GeoImageNet API*:\nPushed docker image: `${env.TAGGED_IMAGE_NAME}`\nDeployed to: https://geoimagenetdev.crim.ca/api/v1"
            }
        }
        // stage('Clean') {
            // Use this command to clean all geoimagenet images on jenkins
        //     sh 'docker rmi $(docker images --format "{{.ID}}: {{.Repository}}" | grep geoimagenet | cut -c 1-12)'
        // }
    }
    post {
       success {
           script {
               coverage = sh(returnStdout: true, script: 'cat ${TEST_OUTPUT}/coverage.out | sed -nr "s/TOTAL.+ ([0-9]+%)/\\1/p" | tr -d "\n"')
           }
           slackSend channel: '#geoimagenet-dev',
                     color: 'good',
                     message: "*GeoImageNet API*: Build #${env.BUILD_NUMBER} *successful* on git branch `${env.GIT_LOCAL_BRANCH}` :tada: (<${env.BUILD_URL}|View>)\n(Test coverage: *${coverage}*)"
       }
       failure {
           slackSend channel: '#geoimagenet-dev', color: 'danger', message: "*GeoImageNet API*: Build #${env.BUILD_NUMBER} *failed* on git branch `${env.GIT_LOCAL_BRANCH}` :sweat_smile: (<${env.BUILD_URL}|View>)"
       }
       always {
           junit 'test_output/*.xml'
       }
    }
}