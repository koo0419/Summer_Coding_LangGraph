# graph/builder.py 파일에서 우리가 만든 'graph' 객체를 가져옵니다.
from graph.builder import graph

try:
    # 그래프의 구조를 이미지 데이터로 변환합니다.
    image_data = graph.get_graph().draw_mermaid_png()

    # 이미지 데이터를 'graph.png' 파일로 저장합니다.
    with open("graph.png", "wb") as f:
        f.write(image_data)

    print("✅ 성공! 'graph.png' 파일이 프로젝트 폴더에 생성되었습니다.")
    print("VS Code에서 파일을 클릭해서 확인해보세요.")

except Exception as e:
    print(f"❌ 오류가 발생했습니다: {e}")
    print("그래프 시각화에 필요한 라이브러리가 설치되지 않았을 수 있습니다.")
    print("터미널에 아래 명령어를 실행해 보세요:")
    print("pip install pygraphviz")