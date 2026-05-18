#include<stdio.h>
int main()
{
    int arr[6] = {2,5,4,3,4,5};
    int elem;
    
    printf("Enter Element To find : ");
    scanf("%d", &elem);
    
    for(int i=0; i<=5; i++)
    {
        if(arr[i] == elem){
            printf("Element found at : %d", i+1, " location");
            return 0;
        }
    }
    return 0;
}