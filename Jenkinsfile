// Jenkinsfile — csv-records-api (FastAPI) + csv-records-ui (React)
// GitHub -> Jenkins -> tests -> Docker build -> Docker Hub -> Minikube -> API & UI tests
//
// Jenkins credentials required (Manage Jenkins -> Credentials):
//   dockerhub-creds      Username with password  (Docker Hub user + access token)
//   kubeconfig-minikube  Secret file             (kubeconfig pointing at https://<minikube ip>:8443)

pipeline {
    agent any

    parameters {
        choice(name: 'DEPLOY_MODE', choices: ['manual', 'auto'],
               description: 'manual = wait for your approval before deploying to Minikube; auto = deploy straight away')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 40, unit: 'MINUTES')
    }

    triggers {
        // Jenkins on a laptop can't receive GitHub webhooks, so poll the repo every ~2 minutes
        pollSCM('H/2 * * * *')
    }

    environment {
        DOCKERHUB_USER = 'saket123'
        API_NAME       = 'csv-records-api'
        UI_NAME        = 'csv-records-ui'
        API_IMAGE      = "docker.io/${DOCKERHUB_USER}/${API_NAME}"
        UI_IMAGE       = "docker.io/${DOCKERHUB_USER}/${UI_NAME}"
        K8S_NAMESPACE  = 'csv-api'
        API_NODE_PORT  = '30080'
        UI_NODE_PORT   = '30081'
    }

    stages {
        stage('Prepare') {
            steps {
                script {
                    env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = "jenkins-${env.BUILD_NUMBER}-${env.GIT_SHORT}"
                }
                echo "Commit ${env.GIT_SHORT} -> tag ${env.IMAGE_TAG}"
                sh 'docker version --format "Docker {{.Server.Version}}" && kubectl version --client'
            }
        }

        stage('Tests') {
            // Both test suites run inside the "test" stage of each Dockerfile
            parallel {
                stage('API: pytest') {
                    steps {
                        sh 'docker build --target test -t ${API_NAME}:test-${BUILD_NUMBER} .'
                    }
                }
                stage('UI: vitest + build') {
                    steps {
                        sh 'docker build --target test -t ${UI_NAME}:test-${BUILD_NUMBER} frontend'
                    }
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build --target runtime \
                      --label org.opencontainers.image.revision=${GIT_SHORT} \
                      -t ${API_IMAGE}:${IMAGE_TAG} -t ${API_IMAGE}:jenkins-latest .
                    docker build --target runtime \
                      --label org.opencontainers.image.revision=${GIT_SHORT} \
                      -t ${UI_IMAGE}:${IMAGE_TAG} -t ${UI_IMAGE}:jenkins-latest frontend
                '''
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        for img in ${API_IMAGE} ${UI_IMAGE}; do
                          docker push $img:${IMAGE_TAG}
                          docker push $img:jenkins-latest
                        done
                    '''
                }
            }
            post {
                always { sh 'docker logout || true' }
            }
        }

        stage('Approve Deploy') {
            // Anything other than "auto" (including the very first build, before parameters exist) waits here
            when { expression { params.DEPLOY_MODE != 'auto' } }
            options { timeout(time: 15, unit: 'MINUTES') }
            steps {
                input message: "Deploy ${env.IMAGE_TAG} (API + UI) to Minikube?", ok: 'Deploy'
            }
        }

        stage('Deploy to Minikube') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    sh '''
                        kubectl apply -f k8s/namespace.yaml
                        kubectl apply -f k8s/configmap.yaml -f k8s/pvc.yaml -f k8s/service.yaml

                        # API (same image is used by the init container that seeds the CSV)
                        sed "s#image: .*${API_NAME}:.*#image: ${API_IMAGE}:${IMAGE_TAG}#" k8s/deployment.yaml \
                          | kubectl apply -f -
                        kubectl -n ${K8S_NAMESPACE} rollout status deployment/${API_NAME} --timeout=180s

                        # UI (Deployment + Service)
                        sed "s#image: .*${UI_NAME}:.*#image: ${UI_IMAGE}:${IMAGE_TAG}#" k8s/frontend.yaml \
                          | kubectl apply -f -
                        kubectl -n ${K8S_NAMESPACE} rollout status deployment/${UI_NAME} --timeout=180s

                        kubectl -n ${K8S_NAMESPACE} get deploy,pods,svc,pvc -o wide
                    '''
                }
            }
        }

        stage('API & UI Tests') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    sh '''
                        set -e
                        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
                        API="http://${NODE_IP}:${API_NODE_PORT}"
                        UI="http://${NODE_IP}:${UI_NODE_PORT}"

                        wait_for() {
                          for i in $(seq 1 30); do
                            curl -fsS "$1" > /dev/null && return 0
                            sleep 2
                          done
                          echo "Not reachable: $1"; return 1
                        }

                        echo "== API ${API}"
                        wait_for "${API}/health"
                        curl -fsS "${API}/health"        | jq -e '.status == "ok"'
                        curl -fsS "${API}/records"       | jq -e '.total >= 0'
                        curl -fsS "${API}/records/stats" | jq -e '.total_records >= 0'
                        curl -fsS "${API}/departments"   | jq -e 'type == "array"'
                        # data can be edited from the UI, so look up a real id instead of assuming id 1
                        FIRST_ID=$(curl -fsS "${API}/records?page_size=1" | jq -r '.items[0].id // empty')
                        if [ -n "$FIRST_ID" ]; then
                          curl -fsS "${API}/records/${FIRST_ID}" | jq -e ".id == ${FIRST_ID}"
                        fi
                        code=$(curl -s -o /dev/null -w '%{http_code}' "${API}/records/999999")
                        [ "$code" = "404" ] || { echo "Expected 404, got $code"; exit 1; }

                        echo "== UI ${UI}"
                        wait_for "${UI}/healthz"
                        curl -fsS "${UI}/" | grep -q '<div id="root">'
                        curl -fsS "${UI}/some/deep/link" | grep -q '<div id="root">'   # SPA fallback
                        curl -fsS "${UI}/api/health" | jq -e '.status == "ok"'         # nginx -> API proxy

                        echo "All API and UI tests passed"
                    '''
                }
            }
            post {
                failure {
                    // Bad release? Roll both apps back to their previous ReplicaSet
                    withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                        sh '''
                            kubectl -n ${K8S_NAMESPACE} rollout undo deployment/${API_NAME} || true
                            kubectl -n ${K8S_NAMESPACE} rollout undo deployment/${UI_NAME} || true
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            // Clean up local images (the pushed ones live on Docker Hub)
            sh '''
                docker rmi ${API_NAME}:test-${BUILD_NUMBER} ${UI_NAME}:test-${BUILD_NUMBER} \
                  ${API_IMAGE}:${IMAGE_TAG} ${API_IMAGE}:jenkins-latest \
                  ${UI_IMAGE}:${IMAGE_TAG} ${UI_IMAGE}:jenkins-latest 2>/dev/null || true
            '''
        }
        success {
            echo "Deployed ${env.IMAGE_TAG}: API on :${env.API_NODE_PORT}, UI on :${env.UI_NODE_PORT} (namespace ${env.K8S_NAMESPACE})"
        }
    }
}
